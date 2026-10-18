namespace SyntheticIpm.Domain;

public enum CampaignState { Draft, Ready, Active, Paused, Finished }

/// <summary>Synthetic lifecycle aggregate; targeting is deliberately separate.</summary>
public sealed class Campaign
{
    private readonly HashSet<Guid> contentIds = [];
    public Guid Id { get; } = Guid.NewGuid();
    public string Name { get; private set; }
    public CampaignState State { get; private set; } = CampaignState.Draft;
    public IReadOnlyCollection<Guid> ContentIds => contentIds.ToArray();
    public Campaign(string name) => Name = Required(name);
    public void Rename(string name) => Name = Required(name);
    public void Associate(Guid contentId)
    {
        if (contentId == Guid.Empty) throw new ArgumentException("Content ID is required.");
        contentIds.Add(contentId);
    }
    public void TransitionTo(CampaignState next)
    {
        var allowed = (State, next) switch
        {
            (CampaignState.Draft, CampaignState.Ready) => true,
            (CampaignState.Ready, CampaignState.Active) => true,
            (CampaignState.Active, CampaignState.Paused or CampaignState.Finished) => true,
            (CampaignState.Paused, CampaignState.Active or CampaignState.Finished) => true,
            _ => false
        };
        if (!allowed) throw new InvalidOperationException($"Transition {State} -> {next} is forbidden.");
        State = next;
    }
    public void EnsureCanDelete()
    {
        if (State == CampaignState.Finished) throw new InvalidOperationException("Finished campaigns cannot be deleted.");
    }
    internal static string Required(string value)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(value);
        return value.Trim();
    }
}
