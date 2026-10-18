using SyntheticIpm.Domain;
namespace SyntheticIpm.Application;

/// <summary>Fictional partner contract. Partner identifiers never become internal GUIDs.</summary>
public sealed record ExternalCampaignDto(string ExternalId, string Title, string Country, int MinimumAge);
public sealed record MappedExternalCampaign(string ExternalId, string Name, TargetAudience Audience);
public static class ExternalCampaignMapper
{
    public static MappedExternalCampaign Map(ExternalCampaignDto dto)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(dto.ExternalId);
        ArgumentException.ThrowIfNullOrWhiteSpace(dto.Title);
        var condition = new TargetingCondition(dto.Country, dto.MinimumAge);
        return new(dto.ExternalId.Trim(), dto.Title.Trim(), new TargetAudience("Imported audience", condition));
    }
}
public sealed class ExternalCampaignService(CampaignService campaigns, IExternalCampaignLinks links)
{
    public Guid Import(ExternalCampaignDto dto)
    {
        var mapped = ExternalCampaignMapper.Map(dto); // Validate everything before mutation.
        var id = links.Find(mapped.ExternalId);
        if (id is not null)
        {
            campaigns.Rename(id.Value, mapped.Name);
            campaigns.SetAudience(id.Value, mapped.Audience);
            return id.Value;
        }
        var campaign = campaigns.Create(mapped.Name);
        campaigns.SetAudience(campaign.Id, mapped.Audience);
        links.Set(mapped.ExternalId, campaign.Id);
        return campaign.Id;
    }
}
