# Judge accuracy against the gold key

- judge source: regrade answer map
- sweep: `/home/robson-tigre/Desktop/everyday-causal-skills/evals/results/sweep-2026-08-04_102745_pid96394`
- answer-map content SHA-256: `d04b64aa709a081af3a938b22ef89f4f50401d2b702ea840104277f25962865d`
- case-input SHA-256: `be2ba0c8ccf7d675fe3cdc153bc24984c784ec006dabbdf2cadda423ec87e957`
- config SHA-256: `dd8c0ec2d1f08d2304b719db621e792554f53a356901e16bfa70cd09c954316f`
- scorer SHA-256: `f2abab7e62676c960a81a3805acb60a96ee66a4352186500620e20c2b004ca5c`

- criteria scored: 68 (10 incomplete)
- gold cells: 326
- judge said yes where the gold label says no (false positive): 42
- judge said no where the gold label says yes (false negative): 5
- criteria where the judge and the gold labels disagree about the gate result: 7

A criterion labelled in fewer than every slot is reported incomplete and has no gold gate result. Its labelled cells still contribute to cell-level false-positive and false-negative totals.

| case | criterion | judge | gold | FP | FN | disagree | to flip |
|---|---|---|---|---|---|---|---|
| did_pedagogy_clean | `explain_parallel_trends_means` | 5/5 | 5/5 | 0 | 0 | no | 2 |
| did_pedagogy_clean | `include_diagnostic_code_alongside` | 5/5 | 4/5 | 1 | 0 | no | 2 |
| did_pedagogy_clean | `mention_future_trends_untestable` | 5/5 | 5/5 | 0 | 0 | no | 2 |
| did_pedagogy_clean | `walk_through_part_regression` | 4/5 | 1/5 | 3 | 0 | yes | 1 |
| exercise_did_quality | `clear_assumptions_student_verify` | 2/5 | 2/5 | 0 | 0 | no | 2 |
| exercise_did_quality | `clearly_state_deliverable` | 5/5 | 5/5 | 0 | 0 | no | 2 |
| exercise_did_quality | `hints_progressive_guiding_students` | 0/5 | 0/5 | 0 | 0 | no | 4 |
| exercise_did_quality | `scenario_describe_realistic_business` | 5/5 | 4 of 5 labelled | 0 | 0 | no | 2 |
| exercise_iv_quality | `avoid_presenting_iv_straightforward` | 4/5 | 4/5 | 0 | 0 | no | 1 |
| exercise_iv_quality | `distinguish_instrument_strength_relevance` | 4/5 | 4/5 | 0 | 0 | no | 1 |
| exercise_iv_quality | `explain_late_through_scenario` | 4/5 | 3/5 | 1 | 0 | yes | 1 |
| exercise_iv_quality | `provide_runnable_code_clear` | 5/5 | 5/5 | 0 | 0 | no | 2 |
| experiments_pedagogy_messy | `explain_precisely_crossover_assignment` | 3/5 | 2/5 | 1 | 0 | no | 1 |
| experiments_pedagogy_messy | `output_itt_and_cace_side_by_side` | 5/5 | 3 of 5 labelled | 0 | 0 | no | 2 |
| experiments_pedagogy_messy | `provide_complete_runnable_code` | 5/5 | 2 of 5 labelled | 0 | 0 | no | 2 |
| experiments_pedagogy_messy | `warn_cace_requires_exclusion` | 5/5 | 5/5 | 0 | 0 | no | 2 |
| hte_interview_guard | `ask_has_pre_specified` | 5/5 | 5/5 | 0 | 0 | no | 2 |
| hte_interview_guard | `ask_outcome_continuous_binary` | 5/5 | 5/5 | 0 | 0 | no | 2 |
| hte_interview_guard | `ask_treatment_randomized_observational` | 5/5 | 5/5 | 0 | 0 | no | 2 |
| iv_pedagogy_clean | `explain_itt_versus_late` | 5/5 | 3 of 5 labelled | 1 | 0 | no | 2 |
| iv_pedagogy_clean | `include_reduced_form_first` | 3/5 | 0/5 | 3 | 0 | no | 1 |
| iv_pedagogy_clean | `mention_late_differ_ate` | 4/5 | 1/5 | 3 | 0 | yes | 1 |
| iv_pedagogy_clean | `provide_complete_2sls_code` | 5/5 | 5/5 | 0 | 0 | no | 2 |
| iv_pedagogy_messy | `explain_stock_yogo_critical_values` | 0/5 | 0/5 | 0 | 0 | no | 4 |
| iv_pedagogy_messy | `explain_weak_instrument_bias` | 5/5 | 5/5 | 0 | 0 | no | 2 |
| iv_pedagogy_messy | `honestly_assess_instrument_strong` | 5/5 | 5/5 | 0 | 0 | no | 2 |
| iv_pedagogy_messy | `include_anderson_rubin_confidence` | 2/5 | 2/5 | 0 | 0 | no | 2 |
| iv_pedagogy_messy | `suggest_alternatives_instrument_too` | 5/5 | 2/5 | 3 | 0 | yes | 2 |
| matching_pedagogy_clean | `distinguish_att_ate_explain` | 5/5 | 1/5 | 4 | 0 | yes | 2 |
| matching_pedagogy_clean | `explain_balance_means_check` | 5/5 | 5/5 | 0 | 0 | no | 2 |
| matching_pedagogy_clean | `explain_estimator_choice_matching` | 2/5 | 2/5 | 0 | 0 | no | 2 |
| matching_pedagogy_clean | `provide_complete_code_balance` | 5/5 | 4 of 5 labelled | 0 | 0 | no | 2 |
| matching_pedagogy_messy | `discuss_fundamental_problem_voluntary` | 5/5 | 5/5 | 0 | 0 | no | 2 |
| matching_pedagogy_messy | `explain_poor_overlap_means` | 5/5 | 5/5 | 0 | 0 | no | 2 |
| matching_pedagogy_messy | `explain_trimming_truncation_bias` | 2/5 | 0/5 | 2 | 0 | no | 2 |
| matching_pedagogy_messy | `provide_code_visualizes_overlap` | 5/5 | 5/5 | 0 | 0 | no | 2 |
| matching_pedagogy_messy | `suggest_alternatives_if_matching_unviable` | 5/5 | 4/5 | 1 | 0 | no | 2 |
| planner_pedagogy_ambiguous | `explain_strengths_limitations_viable` | 5/5 | 4 of 5 labelled | 1 | 0 | no | 2 |
| planner_pedagogy_ambiguous | `flag_opt_endogenous_naive` | 5/5 | 4/5 | 1 | 0 | no | 2 |
| planner_pedagogy_ambiguous | `help_understand_assumptions_hardest` | 4/5 | 4 of 5 labelled | 0 | 0 | no | 1 |
| planner_pedagogy_ambiguous | `identify_first_discriminating_data` | 1/5 | 2/5 | 0 | 1 | no | 3 |
| planner_pedagogy_clear | `multiple_methods_apply_explain` | 5/5 | 5/5 | 0 | 0 | no | 2 |
| planner_pedagogy_clear | `name_provisional_skill_and_prep` | 5/5 | 4/5 | 1 | 0 | no | 2 |
| planner_pedagogy_clear | `produce_structured_plan_clear` | 5/5 | 4 of 5 labelled | 0 | 0 | no | 2 |
| planner_pedagogy_clear | `warn_potential_pitfalls_specific` | 2/5 | 5/5 | 0 | 3 | yes | 2 |
| report_figures_fallback | `attempt_generate_first_stage` | 4/5 | 0/5 | 4 | 0 | yes | 1 |
| report_figures_fallback | `falls_back_to_code_block` | 5/5 | 5/5 | 0 | 0 | no | 2 |
| report_figures_fallback | `include_all_sections_despite` | 5/5 | 5/5 | 0 | 0 | no | 2 |
| report_figures_fallback | `offer_to_help_set_up_r` | 3/5 | 1/5 | 2 | 0 | no | 1 |
| roi_pedagogy_clean | `avoid_overstating_guarantees_forecast` | 4/5 | 4 of 5 labelled | 3 | 0 | no | 1 |
| roi_pedagogy_clean | `breakeven_concept_explained_plain` | 5/5 | 4/5 | 1 | 0 | no | 2 |
| roi_pedagogy_clean | `explain_incremental_plainly_value` | 0/5 | 0/5 | 0 | 0 | no | 4 |
| roi_pedagogy_clean | `recommend_concrete_post_launch` | 5/5 | 5/5 | 0 | 0 | no | 2 |
| roi_pedagogy_clean | `report_breakeven_and_verdict_code` | 5/5 | 5/5 | 0 | 0 | no | 2 |
| timeseries_pedagogy_clean | `compare_causalarima_causalimpact_treating` | 2/5 | 0/5 | 2 | 0 | no | 2 |
| timeseries_pedagogy_clean | `explain_counterfactual_core_idea` | 5/5 | 5/5 | 0 | 0 | no | 2 |
| timeseries_pedagogy_clean | `explain_longer_pre_period_not_enough` | 1/5 | 1/5 | 0 | 0 | no | 3 |
| timeseries_pedagogy_clean | `explain_stationarity_means_matters` | 1/5 | 0/5 | 1 | 0 | no | 3 |
| timeseries_pedagogy_clean | `provide_complete_code_pre` | 5/5 | 4 of 5 labelled | 1 | 0 | no | 2 |
| timeseries_pedagogy_clean | `warn_fundamental_limitation_without` | 5/5 | 5/5 | 0 | 0 | no | 2 |
| timeseries_pedagogy_controls | `explain_causalimpact_uses_control` | 4/5 | 4/5 | 0 | 0 | no | 1 |
| timeseries_pedagogy_controls | `explain_causalimpact_versus_causalarima` | 2/5 | 2/5 | 1 | 1 | no | 2 |
| timeseries_pedagogy_controls | `explain_posterior_tail_area` | 5/5 | 5/5 | 0 | 0 | no | 2 |
| timeseries_pedagogy_controls | `include_visualization_showing_actual` | 1/5 | 0/5 | 1 | 0 | no | 3 |
| timeseries_pedagogy_controls | `warn_controls_unaffected_by_intervention` | 0/5 | 0/5 | 0 | 0 | no | 4 |
| timeseries_pedagogy_messy | `avoid_presenting_break_minor` | 5/5 | 5/5 | 0 | 0 | no | 2 |
| timeseries_pedagogy_messy | `explain_pre_period_structural` | 5/5 | 5/5 | 0 | 0 | no | 2 |
| timeseries_pedagogy_messy | `provide_code_test_visualize` | 5/5 | 5/5 | 0 | 0 | no | 2 |

## Criteria a labeller flagged as possibly unsatisfiable

Recorded with evidence, acting on nothing. No question is reworded, reordered or demoted by this file.

- `include_reduced_form_first` on iv_pedagogy_clean slot 0 — Code prints all three estimates, but no numerical results are included. Requiring full-sample results is questionable because only five of 1,000 rows are visible.
- `include_reduced_form_first` on iv_pedagogy_clean slot 1 — Code prints all three estimates, but no numerical results are included. Requiring full-sample results is questionable because only five of 1,000 rows are visible.
- `include_reduced_form_first` on iv_pedagogy_clean slot 2 — Code prints all three estimates, but no numerical results are included. Requiring full-sample results is questionable because only five of 1,000 rows are visible.
- `include_reduced_form_first` on iv_pedagogy_clean slot 3 — Code prints all three estimates, but no numerical results are included. Requiring full-sample results is questionable because only five of 1,000 rows are visible.
- `include_reduced_form_first` on iv_pedagogy_clean slot 4 — Code prints all three estimates, but no numerical results are included. Requiring full-sample results is questionable because only five of 1,000 rows are visible.
