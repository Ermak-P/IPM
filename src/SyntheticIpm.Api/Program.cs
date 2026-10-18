using SyntheticIpm.Application;
using SyntheticIpm.Domain;
using SyntheticIpm.Infrastructure;

var builder = WebApplication.CreateBuilder(args);
builder.Services.AddSyntheticIpm();
var app = builder.Build();
// ponytail: serialize this tiny in-memory fixture; use transactional storage for concurrent workloads.
using var requests = new SemaphoreSlim(1, 1);
app.Use(async (context, next) =>
{
    await requests.WaitAsync(context.RequestAborted);
    try
    {
        await next(context);
    }
    catch (Exception error) when (error is ArgumentException or InvalidOperationException or KeyNotFoundException)
    {
        context.Response.StatusCode = error switch
        {
            KeyNotFoundException => StatusCodes.Status404NotFound,
            InvalidOperationException => StatusCodes.Status409Conflict,
            _ => StatusCodes.Status400BadRequest
        };
        await context.Response.WriteAsJsonAsync(new { error = error.Message });
    }
    finally { requests.Release(); }
});
app.MapGet("/health", () => Results.Ok(new { status = "synthetic-fixture" }));
app.MapPost("/campaigns", (CampaignInput input, CampaignService service) =>
{
    var campaign = service.Create(input.Name);
    return Results.Created($"/campaigns/{campaign.Id}", CampaignView.From(campaign));
});
app.MapGet("/campaigns/{id:guid}", (Guid id, CampaignService service) => CampaignView.From(service.Get(id)));
app.MapPut("/campaigns/{id:guid}", (Guid id, CampaignInput input, CampaignService service) =>
{
    service.Rename(id, input.Name);
    return Results.NoContent();
});
app.MapPost("/campaigns/{id:guid}/state", (Guid id, StateInput input, CampaignService service) =>
{
    service.Transition(id, input.State);
    return Results.NoContent();
});
app.MapDelete("/campaigns/{id:guid}", (Guid id, CampaignService service) =>
{
    service.Delete(id);
    return Results.NoContent();
});
app.MapPost("/content", (ContentInput input, ContentService service) =>
{
    var item = service.Create(input.Title, input.Type, input.Body);
    return Results.Ok(new { item.Id, item.Title, item.Type, item.Body });
});
app.MapPost("/content/groups", (GroupInput input, ContentService service) =>
{
    var group = service.CreateGroup(input.Name, input.ItemIds);
    return Results.Ok(new { group.Id, group.Name, group.ItemIds });
});
app.MapPost("/campaigns/{id:guid}/content/{contentId:guid}", (Guid id, Guid contentId, CampaignService service) =>
{
    service.AssociateContent(id, contentId);
    return Results.NoContent();
});
app.MapPut("/campaigns/{id:guid}/audience", (Guid id, AudienceInput input, CampaignService service) =>
{
    service.SetAudience(id, new TargetAudience(input.Name, new TargetingCondition(input.Country, input.MinimumAge)));
    return Results.NoContent();
});
app.MapPost("/campaigns/{id:guid}/publish", (Guid id, UserInput input, DistributionService service) =>
    service.Publish(id, new UserProfile(input.UserId, input.Country, input.Age)));
app.MapPost("/campaigns/{id:guid}/interactions", (Guid id, InteractionInput input, InteractionService service) =>
{
    service.Record(id, input.UserId);
    return Results.Accepted();
});
app.MapPost("/external/campaigns", (ExternalCampaignDto input, ExternalCampaignService service) =>
    Results.Ok(new { campaignId = service.Import(input) }));
app.MapPost("/statistics/process", (StatisticsService service) => Results.Ok(new { processed = service.ProcessPending() }));
app.MapGet("/statistics/{id:guid}", (Guid id, StatisticsService service) => service.Get(id));
app.Run();

public sealed record CampaignInput(string Name);
public sealed record StateInput(CampaignState State);
public sealed record ContentInput(string Title, ContentType Type, string Body);
public sealed record GroupInput(string Name, Guid[] ItemIds);
public sealed record AudienceInput(string Name, string Country, int MinimumAge);
public sealed record UserInput(string UserId, string Country, int Age);
public sealed record InteractionInput(string UserId);
public sealed record CampaignView(Guid Id, string Name, CampaignState State, IReadOnlyCollection<Guid> ContentIds)
{
    public static CampaignView From(Campaign campaign) => new(campaign.Id, campaign.Name, campaign.State, campaign.ContentIds);
}
