using Microsoft.Extensions.DependencyInjection;
using SyntheticIpm.Application;
using SyntheticIpm.Domain;
namespace SyntheticIpm.Infrastructure;

public sealed class InMemoryCampaignRepository : ICampaignRepository
{
    private readonly Dictionary<Guid, Campaign> campaigns = [];
    public Campaign Get(Guid id) => campaigns.TryGetValue(id, out var campaign) ? campaign : throw new KeyNotFoundException("Campaign not found.");
    public void Add(Campaign campaign) => campaigns.Add(campaign.Id, campaign);
    public void Remove(Guid id) => campaigns.Remove(id);
}
public sealed class InMemoryContentRepository : IContentRepository
{
    private readonly Dictionary<Guid, ContentItem> items = [];
    private readonly Dictionary<Guid, ContentGroup> groups = [];
    public ContentItem Get(Guid id) => items.TryGetValue(id, out var item) ? item : throw new KeyNotFoundException("Content not found.");
    public void Add(ContentItem item) => items.Add(item.Id, item);
    public ContentGroup GetGroup(Guid id) => groups.TryGetValue(id, out var group) ? group : throw new KeyNotFoundException("Group not found.");
    public void AddGroup(ContentGroup group) => groups.Add(group.Id, group);
}
public sealed class InMemoryTargetAudienceRepository : ITargetAudienceRepository
{
    private readonly Dictionary<Guid, TargetAudience> audiences = [];
    public TargetAudience Get(Guid id) => audiences.TryGetValue(id, out var audience) ? audience : throw new KeyNotFoundException("Audience not configured.");
    public void Set(Guid id, TargetAudience audience) => audiences[id] = audience;
    public void Remove(Guid id) => audiences.Remove(id);
}
public sealed class InMemoryDistributionState : IDistributionState
{
    private readonly Dictionary<Guid, CampaignState> states = [];
    public CampaignState? Get(Guid id) => states.TryGetValue(id, out var state) ? state : null;
    public void Set(Guid id, CampaignState state) => states[id] = state;
    public void Remove(Guid id) => states.Remove(id);
}
/// <summary>Fictional Kafka-like topic: FIFO queue, explicit consumer pump, no broker.</summary>
public sealed class InMemoryMarketingEventTransport : IMarketingEventTransport
{
    private readonly Queue<MarketingEvent> messages = [];
    public void Publish(MarketingEvent message)
    {
        if (message.EventId == Guid.Empty || message.CampaignId == Guid.Empty || !Enum.IsDefined(message.Kind))
            throw new ArgumentException("Invalid event identifiers or kind.");
        ArgumentException.ThrowIfNullOrWhiteSpace(message.UserId);
        messages.Enqueue(message);
    }
    public IReadOnlyList<MarketingEvent> Drain()
    {
        var pending = messages.ToArray();
        messages.Clear();
        return pending;
    }
}
public sealed class InMemoryExternalCampaignLinks : IExternalCampaignLinks
{
    private readonly Dictionary<string, Guid> links = new(StringComparer.Ordinal);
    public Guid? Find(string externalId) => links.TryGetValue(externalId, out var id) ? id : null;
    public void Set(string externalId, Guid campaignId) => links[externalId] = campaignId;
}
public static class DependencyInjection
{
    public static IServiceCollection AddSyntheticIpm(this IServiceCollection services) => services
        .AddSingleton<ICampaignRepository, InMemoryCampaignRepository>()
        .AddSingleton<IContentRepository, InMemoryContentRepository>()
        .AddSingleton<ITargetAudienceRepository, InMemoryTargetAudienceRepository>()
        .AddSingleton<IDistributionState, InMemoryDistributionState>()
        .AddSingleton<IMarketingEventTransport, InMemoryMarketingEventTransport>()
        .AddSingleton<IExternalCampaignLinks, InMemoryExternalCampaignLinks>()
        .AddSingleton<CampaignStateSynchronizer>()
        .AddSingleton<CampaignService>()
        .AddSingleton<ContentService>()
        .AddSingleton<TargetingService>()
        .AddSingleton<DistributionService>()
        .AddSingleton<InteractionService>()
        .AddSingleton<StatisticsService>()
        .AddSingleton<ExternalCampaignService>();
}
