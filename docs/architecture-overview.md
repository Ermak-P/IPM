# Architecture overview

This is a synthetic host application, not an architecture extraction system.

## Projects and intentional boundaries

Domain contains Campaign, content/group models and targeting logic. It references
only the .NET framework. Application contains repository/event ports, DTO mapping,
workflow services, statistics and state synchronization. Infrastructure supplies
in-memory adapters and the dependency injection composition extension. Api supplies
minimal HTTP routes, explicit request/response records and error translation.
Tests use NUnit: UnitTests exercises domain invariants; IntegrationTests composes
real services and adapters through DI, without HTTP or external infrastructure.

Business decisions live in Domain/Application. Transport routes delegate to services.
All services/adapters are process-wide singletons. The API serializes requests with
a semaphore because these intentionally small dictionaries and workflows are not
concurrent transactional storage. Call application services sequentially outside HTTP.

## Call paths

1. Create/rename/transition/delete: HTTP -> CampaignService -> Campaign aggregate ->
   repository. Create/transition -> CampaignStateSynchronizer -> IDistributionState.
   Delete checks the aggregate rule before removing repository/audience/projection.
2. Associate: HTTP -> CampaignService -> IContentRepository.Get -> Campaign.Associate.
3. Publish: HTTP -> DistributionService -> campaign + projected state + content ->
   TargetingService -> TargetingEvaluator -> IMarketingEventTransport.Publish.
4. Statistics: HTTP process endpoint -> StatisticsService.ProcessPending -> transport
   Drain -> totals keyed by campaign GUID, with event-ID deduplication.
5. External import: HTTP -> ExternalCampaignService -> ExternalCampaignMapper ->
   CampaignService + IExternalCampaignLinks. Mapping validates all fields before mutation.
6. Interaction: HTTP -> InteractionService -> campaign existence + user validation ->
   same event transport -> statistics on the next explicit consumer pump.

State data flows one way from campaign management to distribution. Statistics data
flows one way from producers through the transport to statistics. These relationships
are intentional examples for future definition/reference/call-graph analysis.
There is no reverse reference from Domain or Application to Infrastructure or Api.

## HTTP contracts

JSON uses camelCase properties and numeric enums. GUID path parameters identify
internal entities. CampaignState: Draft=0, Ready=1, Active=2, Paused=3, Finished=4.
ContentType: Banner=1, Modal=2, Inline=3. A successful mutation returns 204 unless noted.

| Method and path | Request / response |
|---|---|
| GET /health | 200 status |
| POST /campaigns | `{name}` -> 201 CampaignView `{id,name,state,contentIds}` |
| GET /campaigns/{id} | 200 CampaignView |
| PUT /campaigns/{id} | `{name}` |
| POST /campaigns/{id}/state | `{state}` |
| DELETE /campaigns/{id} | Delete after aggregate validation |
| POST /content | `{title,type,body}` -> 200 item |
| POST /content/groups | `{name,itemIds}` -> 200 group |
| POST /campaigns/{id}/content/{contentId} | Associate existing item |
| PUT /campaigns/{id}/audience | `{name,country,minimumAge}` |
| POST /campaigns/{id}/publish | `{userId,country,age}` -> 200 `{eventId,campaignId,contentIds}` |
| POST /campaigns/{id}/interactions | `{userId}` -> 202 |
| POST /external/campaigns | `{externalId,title,country,minimumAge}` -> 200 `{campaignId}` |
| POST /statistics/process | No body -> 200 `{processed}` |
| GET /statistics/{id} | 200 `{impressions,interactions}`; zero if no consumed events |

Argument errors map to 400, missing entities/audiences to 404, lifecycle and publication
conflicts to 409; application errors use `{error}`. Malformed JSON is handled by ASP.NET.
All endpoints are local fixture contracts with no authentication or versioning promise.
