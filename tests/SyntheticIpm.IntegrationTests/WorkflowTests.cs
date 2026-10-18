using Microsoft.Extensions.DependencyInjection;
using NUnit.Framework;
using SyntheticIpm.Application;
using SyntheticIpm.Domain;
using SyntheticIpm.Infrastructure;
namespace SyntheticIpm.IntegrationTests;
public class WorkflowTests
{
    private ServiceProvider provider = null!;
    private CampaignService campaigns = null!;
    private ContentService content = null!;
    [SetUp]
    public void SetUp()
    {
        provider = new ServiceCollection().AddSyntheticIpm().BuildServiceProvider();
        campaigns = provider.GetRequiredService<CampaignService>();
        content = provider.GetRequiredService<ContentService>();
    }
    [TearDown] public void TearDown() => provider.Dispose();
    private Campaign Prepare(bool associate = true, bool activate = true)
    {
        var campaign = campaigns.Create("Fictional onboarding");
        if (associate)
        {
            var item = content.Create("Hello", ContentType.Banner, "Explore the demo");
            campaigns.AssociateContent(campaign.Id, item.Id);
        }
        campaigns.SetAudience(campaign.Id, new TargetAudience("GB adults", new TargetingCondition("GB", 18)));
        if (activate)
        {
            campaigns.Transition(campaign.Id, CampaignState.Ready);
            campaigns.Transition(campaign.Id, CampaignState.Active);
        }
        return campaign;
    }
    [Test]
    public void Publish_emits_impression_then_statistics_consumes_without_campaign_reference()
    {
        var campaign = Prepare();
        var distribution = provider.GetRequiredService<DistributionService>();
        var statistics = provider.GetRequiredService<StatisticsService>();
        var receipt = distribution.Publish(campaign.Id, new UserProfile("demo-user", "GB", 23));
        Assert.That(receipt.CampaignId, Is.EqualTo(campaign.Id));
        Assert.That(statistics.Get(campaign.Id).Impressions, Is.Zero);
        Assert.That(statistics.ProcessPending(), Is.EqualTo(1));
        Assert.That(statistics.Get(campaign.Id).Impressions, Is.EqualTo(1));
        provider.GetRequiredService<InteractionService>().Record(campaign.Id, "demo-user");
        Assert.That(statistics.ProcessPending(), Is.EqualTo(1));
        Assert.That(statistics.Get(campaign.Id).Interactions, Is.EqualTo(1));
        Assert.That(statistics.ProcessPending(), Is.Zero);
    }
    [TestCase(false, true, "GB", 23)]
    [TestCase(true, false, "GB", 23)]
    [TestCase(true, true, "US", 23)]
    [TestCase(true, true, "GB", 15)]
    public void Invalid_publication_emits_no_event(bool associate, bool activate, string country, int age)
    {
        var campaign = Prepare(associate, activate);
        Assert.Throws<InvalidOperationException>(() => provider.GetRequiredService<DistributionService>()
            .Publish(campaign.Id, new UserProfile("demo-user", country, age)));
        Assert.That(provider.GetRequiredService<StatisticsService>().ProcessPending(), Is.Zero);
    }
    [Test]
    public void State_sync_revokes_distribution_and_deletion_guard_is_enforced()
    {
        var campaign = Prepare();
        var states = provider.GetRequiredService<IDistributionState>();
        Assert.That(states.Get(campaign.Id), Is.EqualTo(CampaignState.Active));
        campaigns.Transition(campaign.Id, CampaignState.Finished);
        Assert.That(states.Get(campaign.Id), Is.EqualTo(CampaignState.Finished));
        Assert.Throws<InvalidOperationException>(() => campaigns.Delete(campaign.Id));
        Assert.That(campaigns.Get(campaign.Id).State, Is.EqualTo(CampaignState.Finished));
        Assert.Throws<InvalidOperationException>(() => provider.GetRequiredService<DistributionService>()
            .Publish(campaign.Id, new UserProfile("demo-user", "GB", 23)));
    }
    [Test]
    public void Draft_deletion_clears_repository_and_projection()
    {
        var campaign = campaigns.Create("Draft");
        campaigns.Delete(campaign.Id);
        Assert.Throws<KeyNotFoundException>(() => campaigns.Get(campaign.Id));
        Assert.That(provider.GetRequiredService<IDistributionState>().Get(campaign.Id), Is.Null);
    }
    [Test]
    public void External_import_maps_and_updates_same_campaign()
    {
        var imports = provider.GetRequiredService<ExternalCampaignService>();
        var id = imports.Import(new ExternalCampaignDto("partner-demo-1", " Welcome ", "GB", 18));
        var updated = imports.Import(new ExternalCampaignDto("partner-demo-1", "Updated", "US", 21));
        Assert.That(updated, Is.EqualTo(id));
        Assert.That(campaigns.Get(id).Name, Is.EqualTo("Updated"));
        Assert.That(provider.GetRequiredService<ITargetAudienceRepository>().Get(id).Condition.Country, Is.EqualTo("US"));
    }
    [Test]
    public void Invalid_import_does_not_partially_update_existing_campaign()
    {
        var imports = provider.GetRequiredService<ExternalCampaignService>();
        var id = imports.Import(new ExternalCampaignDto("partner-demo-1", "Original", "GB", 18));
        Assert.Throws<ArgumentOutOfRangeException>(() => imports.Import(new ExternalCampaignDto("partner-demo-1", "Changed", "GB", -1)));
        Assert.That(campaigns.Get(id).Name, Is.EqualTo("Original"));
        Assert.Throws<ArgumentException>(() => imports.Import(new ExternalCampaignDto("", "Title", "GB", 18)));
    }
    [Test]
    public void Missing_audience_and_content_reference_are_rejected()
    {
        var campaign = campaigns.Create("Draft");
        Assert.Throws<KeyNotFoundException>(() => campaigns.AssociateContent(campaign.Id, Guid.NewGuid()));
        Assert.Throws<KeyNotFoundException>(() => provider.GetRequiredService<ITargetAudienceRepository>().Get(campaign.Id));
    }
    [Test]
    public void Content_group_keeps_association()
    {
        var item = content.Create("Demo", ContentType.Inline, "Body");
        var group = content.CreateGroup("Onboarding", [item.Id]);
        Assert.That(content.GetGroup(group.Id).ItemIds, Does.Contain(item.Id));
    }
    [Test]
    public void Repeated_event_id_is_counted_once()
    {
        var transport = provider.GetRequiredService<IMarketingEventTransport>();
        var message = new MarketingEvent(Guid.NewGuid(), Guid.NewGuid(), "demo-user", MarketingEventKind.Impression);
        transport.Publish(message);
        transport.Publish(message);
        var statistics = provider.GetRequiredService<StatisticsService>();
        Assert.That(statistics.ProcessPending(), Is.EqualTo(1));
        Assert.That(statistics.Get(message.CampaignId).Impressions, Is.EqualTo(1));
    }
    [Test]
    public void Active_campaign_without_audience_emits_no_event()
    {
        var campaign = campaigns.Create("No audience");
        var item = content.Create("Demo", ContentType.Modal, "Body");
        campaigns.AssociateContent(campaign.Id, item.Id);
        campaigns.Transition(campaign.Id, CampaignState.Ready);
        campaigns.Transition(campaign.Id, CampaignState.Active);
        Assert.Throws<KeyNotFoundException>(() => provider.GetRequiredService<DistributionService>()
            .Publish(campaign.Id, new UserProfile("user", "GB", 20)));
        Assert.That(provider.GetRequiredService<StatisticsService>().ProcessPending(), Is.Zero);
    }
    [Test]
    public void Stale_projection_prevents_publication()
    {
        var campaign = Prepare();
        provider.GetRequiredService<IDistributionState>().Set(campaign.Id, CampaignState.Paused);
        Assert.Throws<InvalidOperationException>(() => provider.GetRequiredService<DistributionService>()
            .Publish(campaign.Id, new UserProfile("user", "GB", 20)));
        Assert.That(provider.GetRequiredService<StatisticsService>().ProcessPending(), Is.Zero);
    }
    [Test]
    public void Invalid_content_group_inputs_are_rejected()
    {
        Assert.Throws<ArgumentNullException>(() => content.CreateGroup("Demo", null!));
        Assert.Throws<KeyNotFoundException>(() => content.CreateGroup("Demo", [Guid.NewGuid()]));
    }}

