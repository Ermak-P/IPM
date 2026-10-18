"""Offline declared .NET metadata. This module never evaluates MSBuild."""
from dataclasses import dataclass, field
from fnmatch import fnmatchcase
import hashlib
import json
import ntpath
import os
from pathlib import Path, PurePosixPath
import posixpath
import re
import stat
from typing import Protocol
from xml.parsers import expat

from population_scan import DEFAULT_EXCLUSIONS, SOURCE_KINDS, exclusion_patterns

MAX_BYTES = 2 * 1024 * 1024
MAX_NODES = 20000
MAX_DEPTH = 128
MAX_VALUE = 4096
MSBUILD_NS = 'http://schemas.microsoft.com/developer/msbuild/2003'
EXPRESSION = re.compile(r'[$@%]\(')
GUID = r'\{[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}\}'
SLN_PROJECT = re.compile(
    r'Project\("(' + GUID + r')"\)\s*=\s*"([^"]*)",\s*"([^"]*)",\s*"(' + GUID + r')"')
SOLUTION_FOLDER = '{2150e333-8fdc-42a3-9474-1a3956d46de8}'


class Analyzer(Protocol):
    def extract(self, root: Path, inventory: dict) -> dict: ...


class UnsafeInput(ValueError):
    pass


@dataclass
class Node:
    tag: str
    attrs: dict
    line: int
    column: int
    selector: str
    children: list = field(default_factory=list)
    text: str = ''
    counts: dict = field(default_factory=dict)


def safe_xml(data):
    """Expat with DTD/entity rejection before expansion; bounded tree and input."""
    parser = expat.ParserCreate(namespace_separator='}')
    stack, roots = [], []
    count = 0

    def reject(*args):
        raise UnsafeInput('xml-dtd-or-entity-forbidden')

    def start(tag, attrs):
        nonlocal count
        count += 1
        if count > MAX_NODES or len(stack) >= MAX_DEPTH:
            raise UnsafeInput('xml-resource-limit')
        if '}' in tag:
            namespace, tag = tag.rsplit('}', 1)
            if namespace != MSBUILD_NS:
                raise UnsafeInput('unsupported-xml-namespace')
        if any('}' in key for key in attrs):
            raise UnsafeInput('unsupported-xml-attribute-namespace')
        siblings = stack[-1].children if stack else roots
        counts = stack[-1].counts if stack else {}
        index = counts.get(tag, 0) + 1
        counts[tag] = index
        selector = (stack[-1].selector if stack else '') + f'/{tag}[{index}]'
        node = Node(tag, attrs, parser.CurrentLineNumber,
                    parser.CurrentColumnNumber + 1, selector)
        siblings.append(node)
        stack.append(node)

    def text(value):
        if stack:
            stack[-1].text += value

    parser.StartElementHandler = start
    parser.EndElementHandler = lambda tag: stack.pop()
    parser.CharacterDataHandler = text
    parser.StartDoctypeDeclHandler = reject
    parser.EntityDeclHandler = reject
    parser.ExternalEntityRefHandler = reject
    parser.SkippedEntityHandler = reject
    parser.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
    parser.Parse(data, True)
    return roots[0]


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True)


def safe_relative(name):
    if (not isinstance(name, str) or not name or '\\' in name or ':' in name
            or name.startswith('/') or any(ord(c) < 32 for c in name)):
        return False
    parts = name.split('/')
    return all(part not in ('', '.', '..') for part in parts)


def read_source(root, name, patterns):
    if not safe_relative(name):
        raise UnsafeInput('unsafe-inventory-path')
    parts = name.split('/')
    for i, part in enumerate(parts):
        relative = '/'.join(parts[:i + 1])
        if any(fnmatchcase(relative if '/' in p else part, p) for p in patterns):
            raise UnsafeInput('excluded-inventory-path')
        path = root.joinpath(*parts[:i + 1])
        if path.is_symlink() or path.is_junction():
            raise UnsafeInput('linked-source')
        mode = path.lstat().st_mode
        if i < len(parts) - 1 and not stat.S_ISDIR(mode):
            raise UnsafeInput('unsafe-source-parent')
        if i == len(parts) - 1 and not stat.S_ISREG(mode):
            raise UnsafeInput('source-not-regular-file')
    # O_NOFOLLOW is an extra POSIX safeguard, not a substitute for a stable tree.
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0))
    with os.fdopen(fd, 'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise UnsafeInput('source-not-regular-file')
        data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise UnsafeInput('source-size-limit')
    return data


class DotNetAnalyzer:
    def extract(self, root: Path, inventory: dict) -> dict:
        # A run object keeps analyzer instances reusable without shared state.
        return _Extraction(root, inventory).run()


class _Extraction:
    def __init__(self, root, inventory):
        self.root = Path(root)
        self.inventory = inventory
        self.candidates = {}
        self.diagnostics = []
        self.projects = set()
        self.source = '.'
        self.digest = ''
        self.method = ''

    def diagnostic(self, code, node=None, severity='warning'):
        item = {'source': self.source, 'code': code, 'severity': severity}
        if node:
            item['location'] = self.location(node)
        self.diagnostics.append(item)

    @staticmethod
    def location(node):
        return {'line': node.line, 'column': node.column, 'selector': node.selector}

    def emit(self, kind, value, node, conditions=()):
        serialized = canonical_json({'value': value, 'conditions': conditions})
        if len(serialized) > MAX_VALUE:
            self.diagnostic('metadata-size-limit', node, 'error')
            return
        identity_value = {key: item for key, item in value.items() if key != 'resolution'}
        identity = {'analyzer': 'dotnet-declarations-v1', 'source': self.source,
                    'kind': kind, 'value': identity_value, 'conditions': list(conditions)}
        identifier = 'dotnet.' + hashlib.sha256(canonical_json(identity).encode()).hexdigest()
        evidence = {'source': self.source, 'location': self.location(node),
                    'content_hash': self.digest,
                    'provenance': {'actor': 'dotnet-metadata-extractor',
                                   'method': self.method}}
        if identifier in self.candidates:
            self.diagnostic('duplicate-declaration', node)
            self.candidates[identifier]['evidence'].append(evidence)
        else:
            self.candidates[identifier] = dict(
                id=identifier, kind=kind, source=self.source, value=value,
                conditions=list(conditions), evidence=[evidence],
                interpretation='declared-not-evaluated')
        if EXPRESSION.search(serialized):
            self.diagnostic('unresolved-msbuild-expression', node)

    def conditions(self, node, inherited):
        condition = node.attrs.get('Condition')
        return inherited + ([condition] if condition is not None else [])

    def attributes(self, node, allowed):
        if set(node.attrs) - set(allowed):
            self.diagnostic('unsupported-attributes', node)

    def target(self, raw, node):
        if EXPRESSION.search(raw):
            self.diagnostic('unresolved-msbuild-expression', node)
            return None, 'unresolved-expression'
        path = raw.replace('\\', '/')
        if (not path or path != path.strip() or path.startswith('/')
                or ntpath.splitdrive(raw)[0] or any(c in path for c in '*?;:%')
                or any(ord(c) < 32 for c in path)):
            self.diagnostic('unsupported-reference-path', node)
            return None, 'unsupported-path'
        target = posixpath.normpath(posixpath.join(posixpath.dirname(self.source), path))
        if not safe_relative(target):
            self.diagnostic('reference-outside-root', node)
            return None, 'outside-root'
        if PurePosixPath(target).suffix.lower() != '.csproj':
            self.diagnostic('unsupported-project-type', node)
            return target, 'unsupported-project-type'
        if target not in self.projects:
            self.diagnostic('reference-not-in-inventory', node)
            return target, 'not-in-inventory'
        return target, 'discovered'

    def property(self, node, conditions):
        self.attributes(node, ['Condition'])
        conditions = self.conditions(node, conditions)
        if node.children:
            self.diagnostic('unsupported-nested-metadata', node)
            return
        value = node.text.strip()
        self.emit('project_property', {'name': node.tag, 'declared': value}, node, conditions)
        if not value:
            self.diagnostic('empty-declaration', node)

    def reference(self, node, conditions):
        conditions = self.conditions(node, conditions)
        allowed = ['Include', 'Condition']
        if node.tag == 'PackageReference':
            allowed += ['Version', 'VersionOverride']
        self.attributes(node, allowed)
        # Update/Remove/Exclude and item transforms are not equivalent to Include.
        if 'Include' not in node.attrs or set(node.attrs) & {'Update', 'Remove', 'Exclude'}:
            self.diagnostic('unsupported-item-operation', node)
            return
        include = node.attrs['Include']
        if node.tag == 'ProjectReference':
            target, resolution = self.target(include, node)
            self.emit('project_reference', {'include': include, 'target': target,
                                           'resolution': resolution}, node, conditions)
        else:
            if not include or any(c in include for c in '*?;'):
                self.diagnostic('unsupported-package-include', node)
            self.emit('package_reference', {'include': include}, node, conditions)
            found_version = False
            for key in ['Version', 'VersionOverride']:
                if key in node.attrs:
                    found_version = True
                    self.emit('package_version', {'include': include, 'name': key,
                                                 'declared': node.attrs[key]}, node, conditions)
            for child in node.children:
                if child.tag in ['Version', 'VersionOverride'] and not child.children:
                    found_version = True
                    self.attributes(child, ['Condition'])
                    self.emit('package_version', {'include': include, 'name': child.tag,
                                                 'declared': child.text.strip()}, child,
                              self.conditions(child, conditions))
                else:
                    self.diagnostic('unsupported-reference-metadata', child)
            if not found_version:
                self.diagnostic('package-version-not-declared', node)
        if node.tag == 'ProjectReference':
            for child in node.children:
                self.diagnostic('unsupported-reference-metadata', child)

    def project(self, tree):
        if tree.tag != 'Project':
            raise UnsafeInput('unexpected-xml-root')
        self.attributes(tree, ['Sdk', 'Condition', 'ToolsVersion', 'DefaultTargets', 'InitialTargets'])
        conditions = self.conditions(tree, [])
        self.emit('project', {'path': self.source, 'name': PurePosixPath(self.source).stem,
                              'name_origin': 'filename'}, tree, conditions)
        self.diagnostic('msbuild-imports-and-evaluation-not-performed', tree)
        for group in tree.children:
            if group.tag not in ['PropertyGroup', 'ItemGroup']:
                self.diagnostic('unsupported-project-construct', group)
                continue
            self.attributes(group, ['Condition', 'Label'])
            inherited = self.conditions(group, conditions)
            for node in group.children:
                if group.tag == 'PropertyGroup' and node.tag in [
                        'ProjectName', 'AssemblyName', 'ProjectGuid',
                        'TargetFramework', 'TargetFrameworks']:
                    self.property(node, inherited)
                elif group.tag == 'ItemGroup' and node.tag in ['ProjectReference', 'PackageReference']:
                    self.reference(node, inherited)
                else:
                    self.diagnostic('unsupported-project-metadata', node)

    def slnx(self, tree):
        if tree.tag != 'Solution':
            raise UnsafeInput('unexpected-xml-root')

        def visit(node):
            self.attributes(node, ['Name'] if node.tag == 'Folder' else [])
            for child in node.children:
                if child.tag == 'Folder':
                    visit(child)
                elif child.tag == 'Project':
                    self.attributes(child, ['Path', 'Id'])
                    if 'Path' not in child.attrs:
                        self.diagnostic('missing-solution-project-path', child, 'error')
                        continue
                    raw = child.attrs['Path']
                    target, resolution = self.target(raw, child)
                    value = {'declared_path': raw, 'target': target, 'resolution': resolution}
                    if 'Id' in child.attrs:
                        value['declared_id'] = child.attrs['Id']
                    self.emit('solution_membership', value, child)
                    for detail in child.children:
                        self.diagnostic('unsupported-solution-construct', detail)
                else:
                    self.diagnostic('unsupported-solution-construct', child)
        visit(tree)

    def sln(self, data):
        text = data.decode('utf-16' if data.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig')
        if not any(line.strip() == 'Microsoft Visual Studio Solution File, Format Version 12.00'
                   for line in text.splitlines()[:4]):
            raise UnsafeInput('unsupported-solution-header')
        for line_number, line in enumerate(text.splitlines(), 1):
            node = Node('Project', {}, line_number, len(line) - len(line.lstrip()) + 1,
                        f'Project(line={line_number})')
            if line.lstrip().startswith(('GlobalSection(', 'ProjectSection(')):
                self.diagnostic('solution-build-metadata-not-evaluated', node)
                continue
            if not re.match(r'Project\s*\(', line.lstrip()):
                continue
            match = SLN_PROJECT.fullmatch(line.strip())
            if not match:
                self.diagnostic('malformed-solution-project', node, 'error')
                continue
            project_type, name, raw, project_id = match.groups()
            if project_type.lower() == SOLUTION_FOLDER:
                continue
            target, resolution = self.target(raw, node)
            self.emit('solution_membership', {
                'name': name, 'declared_path': raw, 'target': target,
                'resolution': resolution, 'declared_id': project_id,
                'project_type_id': project_type}, node)

    def run(self):
        sources = []
        try:
            if self.root.is_symlink() or self.root.is_junction() or not self.root.is_dir():
                raise UnsafeInput('invalid-root')
            self.root = self.root.resolve(strict=True)
            if (not isinstance(self.inventory, dict)
                    or self.inventory.get('command') != 'scan'
                    or self.inventory.get('report_version') != '1.0'
                    or self.inventory.get('ok') is not True):
                raise UnsafeInput('invalid-or-incomplete-inventory')
            patterns = exclusion_patterns(self.inventory.get('exclusions', DEFAULT_EXCLUSIONS))
            sources = self.inventory['sources']
            if not isinstance(sources, list):
                raise UnsafeInput('invalid-inventory-sources')
            names = set()
            for entry in sources:
                name = entry['path']
                if (not safe_relative(name) or name in names
                        or entry.get('kind') not in SOURCE_KINDS.values()
                        or SOURCE_KINDS.get(PurePosixPath(name).suffix.lower()) != entry.get('kind')):
                    raise UnsafeInput('invalid-inventory-source')
                names.add(name)
                if entry['kind'] == 'dotnet-project':
                    self.projects.add(name)
        except (OSError, ValueError, TypeError, KeyError):
            self.diagnostic('invalid-root-or-inventory', severity='error')
            return self.finish()
        for source in sorted(sources, key=lambda item: item['path']):
            self.source = source['path']
            self.method = ('static-sln-declaration-v1' if source['kind'] == 'dotnet-solution'
                           else 'static-xml-declaration-v1')
            saved = dict(self.candidates)
            try:
                data = read_source(self.root, self.source, patterns)
                self.digest = 'sha256:' + hashlib.sha256(data).hexdigest()
                if source['kind'] == 'dotnet-solution':
                    self.sln(data)
                elif source['kind'] == 'dotnet-project':
                    self.project(safe_xml(data))
                else:
                    self.slnx(safe_xml(data))
            except UnsafeInput as error:
                self.candidates = saved
                self.diagnostic(str(error), severity='error')
            except expat.ExpatError as error:
                self.candidates = saved
                node = Node('', {}, error.lineno, error.offset + 1, '')
                self.diagnostic('malformed-xml', node, 'error')
            except (OSError, UnicodeError):
                self.candidates = saved
                self.diagnostic('source-unreadable-or-unsupported-encoding', severity='error')
        return self.finish()

    def finish(self):
        diagnostics = sorted({canonical_json(d): d for d in self.diagnostics}.values(),
                             key=canonical_json)
        candidates = sorted(self.candidates.values(), key=lambda c: c['id'])
        for candidate in candidates:
            candidate['evidence'].sort(key=canonical_json)
        return {'command': 'extract', 'report_version': '1.0',
                'analyzer': 'dotnet-declarations-v1',
                'ok': not any(d['severity'] == 'error' for d in diagnostics),
                'candidates': candidates, 'diagnostics': diagnostics,
                'scan': self.inventory,
                'counts': {'candidates': len(candidates), 'diagnostics': len(diagnostics)},
                'limitations': [
                    'Declarations only; conditions, SDKs, imports and MSBuild expressions are not evaluated.',
                    'Candidates are not canonical records and have no confirmation status or verification timestamp.',
                    'Structural extraction does not establish semantic truth; no canonical writes are performed.',
                    'Use a stable repository tree; concurrent hostile filesystem mutation is not supported.'
                ]}
