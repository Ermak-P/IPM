# Synthetic business rules and test map

Every rule is an original synthetic example.

| Rule | Implementation | Observable tests |
|---|---|---|
| Names must be nonblank and are trimmed | Domain/Campaign.Required, Rename | DomainTests.Empty_campaign_name_is_rejected; Campaign_follows_lifecycle_and_finished_cannot_be_deleted |
| Draft -> Ready -> Active; Active -> Paused/Finished; Paused -> Active/Finished; no other or same-state transitions | Domain/Campaign.TransitionTo | DomainTests.Campaign_follows_lifecycle_and_finished_cannot_be_deleted; Invalid_transition_leaves_state_unchanged |
| Finished campaigns cannot be deleted | Domain/Campaign.EnsureCanDelete, Application/CampaignService.Delete | DomainTests.Campaign_follows_lifecycle_and_finished_cannot_be_deleted; WorkflowTests.State_sync_revokes_distribution_and_deletion_guard_is_enforced |
| Content references must exist; duplicate association is harmless | CampaignService.AssociateContent, Campaign.Associate | DomainTests.Content_is_associated_without_duplicate_ids; WorkflowTests.Missing_audience_and_content_reference_are_rejected |
| Content type must be defined, title/body nonblank | Domain/ContentItem | DomainTests.Unknown_content_type_is_rejected |
| Groups contain existing items | Application/ContentService.CreateGroup | WorkflowTests.Content_group_keeps_association |
| Country matches ignoring case, age >= minimum (0..120); user ID nonblank, age <= 120 | Domain/TargetingCondition, TargetingEvaluator | DomainTests.Targeting_matches_all_conditions |
| Publication requires Active in aggregate and projection, content, matching audience | Application/DistributionService.Publish | WorkflowTests.Invalid_publication_emits_no_event |
| Publication emits one impression; interaction emits separate event; consuming updates counters | DistributionService, InteractionService, StatisticsService | WorkflowTests.Publish_emits_impression_then_statistics_consumes_without_campaign_reference |
| Consume event IDs once per process | StatisticsService.ProcessPending | WorkflowTests.Repeated_event_id_is_counted_once |
| Partner ID/title/country and age must validate before any update; repeated ID updates same campaign | ExternalCampaignMapper, ExternalCampaignService | WorkflowTests.External_import_maps_and_updates_same_campaign; Invalid_import_does_not_partially_update_existing_campaign |
| Creation/transition synchronizes projection; deletion removes it | CampaignService, CampaignStateSynchronizer | WorkflowTests.State_sync_revokes_distribution_and_deletion_guard_is_enforced; Draft_deletion_clears_repository_and_projection |

Source paths above are relative to src/SyntheticIpm.Domain or src/SyntheticIpm.Application;
tests are in tests/SyntheticIpm.UnitTests/DomainTests.cs and
tests/SyntheticIpm.IntegrationTests/WorkflowTests.cs. These are service integration
tests using in-memory implementations, not mocks or tests requiring Kafka/database servers.

