# frozen_string_literal: true

require "minitest/autorun"
require "yaml"

ROOT = File.expand_path("../..", __dir__)

class StudentPassV1PolicyContractTest < Minitest::Test
  def setup
    requirements = YAML.safe_load(
      File.read(File.join(ROOT, "data/official-sources/extracts/student-pass-v1.requirements.yaml")),
      aliases: false
    )
    rule_set = YAML.safe_load(
      File.read(File.join(ROOT, "data/rules/student-pass-v1.yaml")),
      aliases: false
    )

    @requirement = requirements.fetch("requirements").find { |item| item.fetch("id") == "SPV1-REQ-014" }
    @due_rule = rule_set.fetch("rules").find { |item| item.fetch("id") == "SPV1-RULE-014" }
    @overdue_rule = rule_set.fetch("rules").find { |item| item.fetch("id") == "SPV1-RULE-015" }
  end

  def test_requirement_declares_seven_calendar_day_operational_policy
    handling = @requirement.fetch("machine_handling")

    assert_includes handling, "seven calendar days"
    assert_includes handling, "urgent human follow-up"
    assert_includes handling, "never automatically reject"
  end

  def test_due_and_overdue_rules_split_at_day_seven
    due_condition = condition_for(@due_rule, "medical.days_since_arrival")
    overdue_condition = condition_for(@overdue_rule, "medical.days_since_arrival")

    assert_equal({"fact" => "medical.days_since_arrival", "operator" => "lte", "value" => 7}, due_condition)
    assert_equal({"fact" => "medical.days_since_arrival", "operator" => "gte", "value" => 8}, overdue_condition)
  end

  def test_overdue_rule_escalates_without_automatic_rejection
    action = @overdue_rule.fetch("then")

    assert_equal "manual_review", action.fetch("outcome")
    assert_equal "POST_ARRIVAL_MEDICAL_OVERDUE", action.fetch("code")
    assert_equal "urgent_post_arrival_medical_follow_up", action.fetch("create_task")
    assert_includes action.fetch("message"), "seven-calendar-day"
    refute_match(/working-day interpretation/i, action.fetch("message"))
  end

  private

  def condition_for(rule, fact)
    rule.fetch("when").fetch("all").find { |condition| condition.fetch("fact") == fact }
  end
end
