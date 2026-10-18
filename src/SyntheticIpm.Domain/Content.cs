namespace SyntheticIpm.Domain;

/// <summary>Banner: short placement; Modal: overlay; Inline: embedded message. Synthetic values only.</summary>
public enum ContentType { Banner = 1, Modal = 2, Inline = 3 }
public sealed class ContentItem
{
    public Guid Id { get; } = Guid.NewGuid();
    public string Title { get; }
    public ContentType Type { get; }
    public string Body { get; }
    public ContentItem(string title, ContentType type, string body)
    {
        Title = Campaign.Required(title);
        Body = Campaign.Required(body);
        if (!Enum.IsDefined(type)) throw new ArgumentException("Unknown content type.");
        Type = type;
    }
}
public sealed class ContentGroup(string name)
{
    private readonly HashSet<Guid> itemIds = [];
    public Guid Id { get; } = Guid.NewGuid();
    public string Name { get; } = Campaign.Required(name);
    public IReadOnlyCollection<Guid> ItemIds => itemIds.ToArray();
    public void Add(ContentItem item) => itemIds.Add(item.Id);
}
