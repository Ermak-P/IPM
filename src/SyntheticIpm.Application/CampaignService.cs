using SyntheticIpm.Domain;
namespace SyntheticIpm.Application;

public sealed class CampaignStateSynchronizer(IDistributionState state)
{
    public void Synchronize(Campaign campaign) => state.Set(campaign.Id, campaign.State);
    public void Remove(Guid id) => state.Remove(id);
}
public sealed class CampaignService(ICampaignRepository campaigns, IContentRepository content,
    ITargetAudienceRepository audiences, CampaignStateSynchronizer synchronizer)
{
    public Campaign Create(string name)
    {
        var campaign = new Campaign(name);
        campaigns.Add(campaign);
        synchronizer.Synchronize(campaign);
        return campaign;
    }
    public Campaign Get(Guid id) => campaigns.Get(id);
    public void Rename(Guid id, string name) => campaigns.Get(id).Rename(name);
    public void Transition(Guid id, CampaignState next)
    {
        var campaign = campaigns.Get(id);
        campaign.TransitionTo(next);
        synchronizer.Synchronize(campaign);
    }
    public void AssociateContent(Guid id, Guid contentId)
    {
        var item = content.Get(contentId);
        campaigns.Get(id).Associate(item.Id);
    }
    public void SetAudience(Guid id, TargetAudience audience)
    {
        _ = campaigns.Get(id);
        ArgumentException.ThrowIfNullOrWhiteSpace(audience.Name);
        ArgumentNullException.ThrowIfNull(audience.Condition);
        audiences.Set(id, audience);
    }
    public void Delete(Guid id)
    {
        campaigns.Get(id).EnsureCanDelete();
        campaigns.Remove(id);
        audiences.Remove(id);
        synchronizer.Remove(id);
    }
}
public sealed class ContentService(IContentRepository content)
{
    public ContentItem Create(string title, ContentType type, string body)
    {
        var item = new ContentItem(title, type, body);
        content.Add(item);
        return item;
    }
    public ContentGroup CreateGroup(string name, IReadOnlyList<Guid> itemIds)
    {
        ArgumentNullException.ThrowIfNull(itemIds);
        var group = new ContentGroup(name);
        foreach (var id in itemIds) group.Add(content.Get(id));
        content.AddGroup(group);
        return group;
    }
    public ContentGroup GetGroup(Guid id) => content.GetGroup(id);
}

