using SyntheticIpm.Domain;
namespace SyntheticIpm.Application;

public sealed class TargetingService(ITargetAudienceRepository audiences)
{
    public bool IsEligible(Guid campaignId, UserProfile user) => TargetingEvaluator.Matches(audiences.Get(campaignId), user);
}
public sealed record PublicationReceipt(Guid EventId, Guid CampaignId, IReadOnlyCollection<Guid> ContentIds);
public sealed class DistributionService(ICampaignRepository campaigns, IContentRepository content,
    TargetingService targeting, IDistributionState states, IMarketingEventTransport events)
{
    public PublicationReceipt Publish(Guid campaignId, UserProfile user)
    {
        var campaign = campaigns.Get(campaignId);
        if (campaign.State != CampaignState.Active || states.Get(campaignId) != CampaignState.Active)
            throw new InvalidOperationException("Publication requires an active, synchronized campaign.");
        if (campaign.ContentIds.Count == 0) throw new InvalidOperationException("Publication requires content.");
        foreach (var id in campaign.ContentIds) _ = content.Get(id);
        if (!targeting.IsEligible(campaignId, user)) throw new InvalidOperationException("User is outside the target audience.");
        var message = new MarketingEvent(Guid.NewGuid(), campaignId, user.UserId, MarketingEventKind.Impression);
        events.Publish(message);
        return new PublicationReceipt(message.EventId, campaignId, campaign.ContentIds);
    }
}
public sealed class InteractionService(ICampaignRepository campaigns, IMarketingEventTransport events)
{
    public void Record(Guid campaignId, string userId)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(userId);
        _ = campaigns.Get(campaignId);
        events.Publish(new MarketingEvent(Guid.NewGuid(), campaignId, userId.Trim(), MarketingEventKind.Interaction));
    }
}
public sealed record CampaignStatistics(int Impressions, int Interactions);
/// <summary>Consumes only the event contract. Does not read campaign or content repositories.</summary>
public sealed class StatisticsService(IMarketingEventTransport events)
{
    private readonly Dictionary<Guid, CampaignStatistics> totals = [];
    private readonly HashSet<Guid> processed = [];
    public CampaignStatistics Get(Guid campaignId) => totals.GetValueOrDefault(campaignId) ?? new(0, 0);
    public int ProcessPending()
    {
        var count = 0;
        foreach (var message in events.Drain())
        {
            if (!processed.Add(message.EventId)) continue;
            var previous = Get(message.CampaignId);
            totals[message.CampaignId] = message.Kind switch
            {
                MarketingEventKind.Impression => previous with { Impressions = previous.Impressions + 1 },
                MarketingEventKind.Interaction => previous with { Interactions = previous.Interactions + 1 },
                _ => throw new ArgumentException("Unknown event kind.")
            };
            count++;
        }
        return count;
    }
}
