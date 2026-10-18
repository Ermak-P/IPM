using SyntheticIpm.Domain;
namespace SyntheticIpm.Application;

public interface ICampaignRepository
{
    Campaign Get(Guid id);
    void Add(Campaign campaign);
    void Remove(Guid id);
}
public interface IContentRepository
{
    ContentItem Get(Guid id);
    void Add(ContentItem item);
    ContentGroup GetGroup(Guid id);
    void AddGroup(ContentGroup group);
}
public interface ITargetAudienceRepository
{
    TargetAudience Get(Guid campaignId);
    void Set(Guid campaignId, TargetAudience audience);
    void Remove(Guid campaignId);
}
/// <summary>One-way projection: campaign lifecycle -> distribution read state.</summary>
public interface IDistributionState
{
    CampaignState? Get(Guid campaignId);
    void Set(Guid campaignId, CampaignState state);
    void Remove(Guid campaignId);
}
public enum MarketingEventKind { Impression, Interaction }
/// <summary>Transport contract contains identifiers, never campaign aggregates.</summary>
public sealed record MarketingEvent(Guid EventId, Guid CampaignId, string UserId, MarketingEventKind Kind);
/// <summary>Single-topic producer/consumer port; Drain acknowledges delivered events.</summary>
public interface IMarketingEventTransport
{
    void Publish(MarketingEvent message);
    IReadOnlyList<MarketingEvent> Drain();
}
public interface IExternalCampaignLinks
{
    Guid? Find(string externalId);
    void Set(string externalId, Guid campaignId);
}
