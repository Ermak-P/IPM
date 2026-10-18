using NUnit.Framework;
using SyntheticIpm.Domain;
namespace SyntheticIpm.UnitTests;
public class DomainTests
{
    [Test]
    public void Campaign_follows_lifecycle_and_finished_cannot_be_deleted()
    {
        var campaign = new Campaign("  Welcome  ");
        Assert.That(campaign.Name, Is.EqualTo("Welcome"));
        campaign.Rename("New welcome");
        campaign.TransitionTo(CampaignState.Ready);
        campaign.TransitionTo(CampaignState.Active);
        campaign.TransitionTo(CampaignState.Paused);
        campaign.TransitionTo(CampaignState.Active);
        campaign.TransitionTo(CampaignState.Finished);
        Assert.That(campaign.State, Is.EqualTo(CampaignState.Finished));
        Assert.Throws<InvalidOperationException>(campaign.EnsureCanDelete);
    }
    [TestCase(CampaignState.Active)]
    [TestCase(CampaignState.Finished)]
    [TestCase(CampaignState.Draft)]
    [TestCase((CampaignState)99)]
    public void Invalid_transition_leaves_state_unchanged(CampaignState next)
    {
        var campaign = new Campaign("Welcome");
        Assert.Throws<InvalidOperationException>(() => campaign.TransitionTo(next));
        Assert.That(campaign.State, Is.EqualTo(CampaignState.Draft));
    }
    [Test]
    public void Content_is_associated_without_duplicate_ids()
    {
        var campaign = new Campaign("Welcome");
        var item = new ContentItem("Hello", ContentType.Banner, "Welcome aboard");
        campaign.Associate(item.Id);
        campaign.Associate(item.Id);
        Assert.That(campaign.ContentIds, Is.EqualTo(new[] { item.Id }));
    }
    [TestCase("GB", 20, true)]
    [TestCase("US", 20, false)]
    [TestCase("GB", 17, false)]
    public void Targeting_matches_all_conditions(string country, int age, bool expected)
    {
        var audience = new TargetAudience("Adults in GB", new TargetingCondition("GB", 18));
        Assert.That(TargetingEvaluator.Matches(audience, new UserProfile("user", country, age)), Is.EqualTo(expected));
    }
    [TestCase("")]
    [TestCase("   ")]
    public void Empty_campaign_name_is_rejected(string name) =>
        Assert.Throws<ArgumentException>(() => new Campaign(name));
    [Test]
    public void Unknown_content_type_is_rejected() =>
        Assert.Throws<ArgumentException>(() => new ContentItem("Hello", (ContentType)99, "body"));
}
