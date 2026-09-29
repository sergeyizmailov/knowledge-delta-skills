# 15 — Meta Ads MCP: live tool inventory (tools/list, 2026-09-02)

Reviewed 2026-09-03 (tool dump not re-taken since; pointer fixed 2026-09-29).

Dumped from `https://mcp.facebook.com/ads` with a System User bearer token (`scripts/mcp.py tools`). 106 tools. Re-dump when Meta changes the server; the schema is not published. Decision facts live in `02` §6 — this file is the parameter lookup only.

| Tool | Parameters (required in **bold**) |
|---|---|
| `ads_account_get_activity_logs` | **ad_account_id**, object_id, start_time, end_time, event_category, user_id, limit |
| `ads_activate_entity` | **ad_account_id**, **entity_id**, **entity_type**, ignore_validation_errors |
| `ads_boost_ig_post` | **ad_account_id**, **ig_account_id**, **ig_media_id**, daily_budget, duration_days, targeting, call_to_action, objective, campaign_name, buying_type, special_ad_categories, campaign_bid_strategy, campaign_daily_budget, campaign_lifetime_budget, ad_set_name, destination_type, optimization_goal, billing_event, bid_strategy, bid_amount, lifetime_budget, start_time, end_time, promoted_object, ad_name, confirmed |
| `ads_catalog_create` | **business_id**, **catalog_name**, vertical, feed_name, feed_url, feed_username, feed_password, schedule, items, update_only, feed_file_content, feed_file_name, feed_file_type |
| `ads_catalog_create_feed_rule` | **product_feed_id**, **attribute**, **rule_type**, params |
| `ads_catalog_create_product_feed` | **catalog_id**, **name**, feed_type, country, default_currency, schedule |
| `ads_catalog_create_product_feed_upload_session` | **product_feed_id** |
| `ads_catalog_create_product_set` | **catalog_id**, **title**, **filter**, retailer_id |
| `ads_catalog_delete_product` | **product_id** |
| `ads_catalog_event_source_connect` | **catalog_id**, **event_source_id** |
| `ads_catalog_event_source_disconnect` | **catalog_id**, **event_source_id** |
| `ads_catalog_event_source_get` | **catalog_id**, limit |
| `ads_catalog_event_source_get_catalogs` | **event_source_id** |
| `ads_catalog_event_source_get_health` | **catalog_id**, event_source_id, limit |
| `ads_catalog_event_source_get_recommendations` | **catalog_id** |
| `ads_catalog_get_businesses` | limit, cursor, business_name |
| `ads_catalog_get_catalogs` _(deprecated)_ | limit, cursor, business_id, ad_account_id, name |
| `ads_catalog_get_data_sources` | **catalog_id**, limit, cursor |
| `ads_catalog_get_details` _(deprecated)_ | **catalog_id**, feed_limit, feed_cursor, feed_ingestion_source_type, override_type |
| `ads_catalog_get_diagnostics` | **catalog_id**, severity, limit |
| `ads_catalog_get_dynamic_ads_health` | catalog_id, product_set_id, with_issue_only, checks |
| `ads_catalog_get_feed_rules` | **product_feed_id**, limit, cursor |
| `ads_catalog_get_product_details` _(deprecated)_ | **product_id** |
| `ads_catalog_get_product_feed_details` _(deprecated)_ | **product_feed_id** |
| `ads_catalog_get_product_feed_upload_sessions` | **product_feed_id**, limit, cursor |
| `ads_catalog_get_product_product_sets` _(deprecated)_ | **product_id**, name, limit, cursor |
| `ads_catalog_get_product_set_details` _(deprecated)_ | **product_set_id** |
| `ads_catalog_get_product_set_products` _(deprecated)_ | **product_set_id**, limit, cursor, fields, availability, retailer_id, brand, category, condition, product_type, price_min, price_max |
| `ads_catalog_get_product_sets` _(deprecated)_ | **catalog_id**, name, limit, cursor |
| `ads_catalog_list_catalogs` | entity_id, name, limit, cursor |
| `ads_catalog_list_partner_integrations` | **entity_id**, limit, cursor |
| `ads_catalog_list_product_feeds` | **entity_id**, fields, limit, cursor |
| `ads_catalog_list_product_sets` | **entity_id**, name, limit, cursor |
| `ads_catalog_list_products` | **entity_id**, filter, limit, cursor, fields, error_type |
| `ads_catalog_product_create` | **catalog_id**, **retailer_id**, **name**, description, url, image_url, price, sale_price, currency, availability, condition, brand, visibility, properties |
| `ads_catalog_product_feed_delete` | **product_feed_id** |
| `ads_catalog_product_feed_delete_rule` | **feed_rule_id** |
| `ads_catalog_product_set_delete` | **product_set_id** |
| `ads_catalog_search_product` _(deprecated)_ | **catalog_id**, filter, limit, cursor, fields, error_type |
| `ads_catalog_update_catalog` | **catalog_id**, name |
| `ads_catalog_update_product` | **catalog_id**, **retailer_id**, name, description, url, image_url, price, sale_price, currency, availability, condition, brand, visibility, properties |
| `ads_catalog_update_product_feed` | **product_feed_id**, name, default_currency, delimiter, encoding, quoted_fields_mode, replace_schedule, update_schedule, clear_replace_schedule, clear_update_schedule |
| `ads_catalog_update_product_set` | **product_set_id**, name, filter, retailer_id |
| `ads_create_ad` | **ad_account_id**, **ad_set_id**, **ad_name**, creative, bid_amount, tracking_specs, conversion_domain, adlabels, source_ad_id, ad_schedule_start_time, ad_schedule_end_time, display_sequence, engagement_audience, adset_spec |
| `ads_create_ad_set` | **ad_account_id**, **campaign_id**, **ad_set_name**, **billing_event**, **optimization_goal**, **targeting**, daily_budget, lifetime_budget, start_time, end_time, bid_strategy, bid_amount, promoted_object, destination_type, adset_schedule, pacing_type, attribution_spec, frequency_control_specs, is_dynamic_creative, existing_customer_budget_percentage, tune_for_category, bid_constraints, optimization_sub_event, multi_optimization_goal_weight, daily_min_spend_target, daily_spend_cap, lifetime_min_spend_target, lifetime_spend_cap, dsa_beneficiary, dsa_payor, campaign_attribution, is_incremental_attribution_enabled, adlabels, budget_schedule_specs, budget_source, budget_split_set_id, daily_imps, lifetime_imps, max_budget_spend_percentage, min_budget_spend_percentage, io_number, cost_bidding_mode, campaign_spec, campaign_active_time, campaign_targeting_consolidation, source_adset_id, split_test_config_splits_index, automatic_manual_state, calling_settings, naming_template_custom_fields, marketing_goal, biz_ai_enabled_state, saved_audience, saved_audience_id, targeting_as_signal, adjust_lookalikes, brand_audience_id, reporting_audience, placement, placement_soft_opt_out, rf_prediction_id, contextual_bundling_spec, creative_sequence, creative_diversity_data, creative_diversity_label, creative_diversity_score, creative_fatigue_prediction_ple, is_dynamic_creative_format_automation, is_dynamic_creative_optimization, multi_event_conversion_attribution_window_seconds, low_creative_reach, conversion_goal_id, conversion_locations, conversion_value_expression_spec, partnership_ad_content_lists, shops_ads_metadata_tags, is_message_marketing, time_based_ad_rotation_id_blocks, time_based_ad_rotation_intervals, time_start, time_stop, time_suggestion, include_in_ad_study_cell_id, include_in_ad_study_id, lightweight_split_test_options, guidance_lift_estimate, brand_safety_config, breakdown_effect_eligibility, is_lifetime_flex_with_valid_schedule, is_sac_cfca_terms_certified, metrics_metadata, relative_value, value_rule_set_id, value_rules_applied, value_rules_spec |
| `ads_create_campaign` | **ad_account_id**, **campaign_name**, **objective**, **buying_type**, special_ad_categories, campaign_bid_strategy, campaign_daily_budget, campaign_lifetime_budget, campaign_spend_cap, campaign_start_time, campaign_stop_time, promoted_object, special_ad_category_country, is_skadnetwork_attribution, budget_schedule_specs, adlabels, campaign_optimization_type, is_using_l3_schedule, iterative_split_test_configs, source_campaign_id, topline_id |
| `ads_create_creative` | **ad_account_id**, **page_id**, image_hash, image_url, video_id, product_set_id, link_url, display_link, message, description, call_to_action_type, name, headline, instagram_user_id, self_ai_disclosure, object_story_id, advantage_plus_creative, advantage_plus_creative_features, degrees_of_freedom_spec, cards, placement_videos, facebook_partnership_ad |
| `ads_create_custom_audience` | **ad_account_id**, **name**, **subtype**, origin_audience_id, lookalike_ratio, customer_file_source, rule, prefill, audience_labels, description, is_value_based, retention_days |
| `ads_creative_delete` | **creative_id** |
| `ads_creative_update` | **creative_id**, name, status, adlabels, adlabels_operation |
| `ads_creative_upload_image` _(deprecated)_ | **ad_account_id**, **image_url**, name |
| `ads_creative_upload_local_image` | **ad_account_id**, media_kind, **image_name**, **mime_type**, **file_size**, **image_sha256** |
| `ads_creative_upload_media` | **ad_account_id**, **upload_source**, media_type, media_url, name |
| `ads_creative_upload_video` _(deprecated)_ | **ad_account_id**, **video_url**, title |
| `ads_delete_custom_audience` | **custom_audience_id** |
| `ads_delete_local_ad_image` | **ad_account_id**, **image_hash** |
| `ads_experiment_abtest_create_test` | **ad_account_id**, **cells**, test_name, start_time, end_time, primary_kpi, secondary_kpis, budget_percentage |
| `ads_experiment_abtest_get_test` | ad_account_id, **study_id** |
| `ads_experiment_abtest_update_test` | ad_account_id, **study_id**, **action**, reason, test_name, start_time, end_time |
| `ads_experiment_check_eligibility` | **ad_account_id**, ad_entity_ids |
| `ads_experiment_lift_create_test` | **ad_account_id**, study_name, start_time, end_time |
| `ads_experiment_lift_get_test` | **study_id** |
| `ads_experiment_list_tests` | ad_account_id, ad_entity_id, study_type, include_finished, limit |
| `ads_finalize_local_ad_image_upload` | **ad_account_id**, **completion_token** |
| `ads_get_ad_account_custom_audiences` | **ad_account_id**, subtype_filter, limit, cursor |
| `ads_get_ad_account_pages` | **ad_account_id**, cursor, limit |
| `ads_get_ad_accounts` | cursor, limit |
| `ads_get_ad_entities` | **ad_account_id**, fields, level, filtering, breakdowns, sort, time_range, date_preset, time_increment, limit, object_state, object_ids, cursor |
| `ads_get_ad_images` | **ad_account_id**, hashes, name, fields, limit, cursor |
| `ads_get_ad_preview` | ad_id, creative_id, ad_format |
| `ads_get_ad_videos` | **ad_account_id**, video_ids, title, fields, limit, cursor |
| `ads_get_creative_ads` | **creative_id**, limit, cursor |
| `ads_get_creatives` | **ad_account_id**, creative_ids, fields, limit, cursor |
| `ads_get_custom_audience` | **custom_audience_id** |
| `ads_get_custom_audience_adsets` | **custom_audience_id**, limit |
| `ads_get_customconversions` | **ad_account_id**, dataset_id, cursor, limit |
| `ads_get_dataset_details` | **dataset_id** |
| `ads_get_dataset_quality` | **dataset_id**, query_type |
| `ads_get_dataset_stats` | **dataset_id**, event_name, start_time, end_time, aggregation, event_source |
| `ads_get_datasets` | business_id, ad_account_id, cursor, limit |
| `ads_get_errors` | **entity_ids**, limit |
| `ads_get_field_context` | field_names |
| `ads_get_help_article` | **search_query** |
| `ads_get_ig_accounts` | **ad_account_id**, limit, cursor |
| `ads_get_ig_media` | **ad_account_id**, **ig_account_id**, filters, cursor, limit |
| `ads_get_opportunity_score` | **ad_account_id** |
| `ads_get_pages_for_business` | **business_id**, cursor, limit |
| `ads_get_user_pages` | cursor, limit |
| `ads_insights_advertiser_context` | **ad_account_id**, entity_ids, date_preset, date_from, date_to |
| `ads_insights_anomaly_signal` | **ad_account_id**, entity_ids |
| `ads_insights_auction_ranking_benchmarks` | **ad_account_id**, entity_ids, date_preset, date_from, date_to |
| `ads_insights_industry_benchmark` | **ad_account_id**, entity_ids, analysis_metric, date_preset, date_from, date_to, conversation_intent, conversation_topic, cas_segment, optimization_goal_override |
| `ads_insights_performance_trend` | **ad_account_id**, entity_ids, analysis_level, analysis_metric, conversation_intent, conversation_topic |
| `ads_library_search` | search_terms, page_ids, countries, ad_active_status, ad_type, limit |
| `ads_log_ui_interaction` | **interaction_type**, **tool_name**, duration_ms, **ad_account_id**, entity_id, locale |
| `ads_pixel_event_create` | partial, **items** |
| `ads_pixel_event_delete` | partial, **items** |
| `ads_pixel_event_read` | partial, **items** |
| `ads_pixel_event_update` | partial, **items** |
| `ads_pixel_parameter_create` | partial, **items** |
| `ads_pixel_parameter_delete` | partial, **items** |
| `ads_pixel_parameter_read` | partial, **items** |
| `ads_pixel_parameter_update` | partial, **items** |
| `ads_update_custom_audience` | **custom_audience_id**, name, description, rule, audience_labels |
| `ads_update_custom_audience_users` | **audience_id**, operation, **schema**, **data**, customer_consent, debug_identifier |
| `ads_update_entity` | **ad_account_id**, **entity_id**, **entity_type**, **fields** |

Every tool also takes `advertiser_request` and `client_conversation_id` (telemetry strings).
