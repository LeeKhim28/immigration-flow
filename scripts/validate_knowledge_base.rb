# frozen_string_literal: true

require "json"
require "yaml"

ROOT = File.expand_path("..", __dir__)

def load_yaml(path)
  YAML.safe_load(File.read(File.join(ROOT, path)), aliases: false)
end

def assert(condition, message)
  raise message unless condition
end

def fact_value(facts, path)
  path.split(".").reduce(facts) do |value, key|
    return nil unless value.is_a?(Hash)

    value[key]
  end
end

def condition_matches?(condition, facts, datasets)
  return condition.fetch("all").all? { |item| condition_matches?(item, facts, datasets) } if condition.key?("all")
  return condition.fetch("any").any? { |item| condition_matches?(item, facts, datasets) } if condition.key?("any")

  actual = fact_value(facts, condition.fetch("fact"))
  expected = condition["value"]

  case condition.fetch("operator")
  when "eq" then actual == expected
  when "neq" then actual != expected
  when "in" then Array(expected).include?(actual)
  when "not_in" then !Array(expected).include?(actual)
  when "gte" then !actual.nil? && actual >= expected
  when "lte" then !actual.nil? && actual <= expected
  when "present" then !actual.nil?
  when "absent" then actual.nil?
  when "dataset_contains" then Array(datasets.fetch(expected)).include?(actual)
  else raise "Unsupported operator: #{condition.fetch('operator')}"
  end
end

def merge_patch(target, patch)
  return patch unless patch.is_a?(Hash)

  result = target.is_a?(Hash) ? Marshal.load(Marshal.dump(target)) : {}
  patch.each do |key, value|
    if value.nil?
      result.delete(key)
    else
      result[key] = merge_patch(result[key], value)
    end
  end
  result
end

registry = load_yaml("data/official-sources/registry.yaml")
requirements = load_yaml("data/official-sources/extracts/student-pass-v1.requirements.yaml")
sev_dataset = load_yaml("data/official-sources/extracts/sev-required-countries.yaml")
rule_set = load_yaml("data/rules/student-pass-v1.yaml")
cases = load_yaml("tests/rules/student-pass-v1.cases.yaml")

JSON.parse(File.read(File.join(ROOT, "data/official-sources/source-record.schema.json")))
JSON.parse(File.read(File.join(ROOT, "data/official-sources/extracts/requirement-set.schema.json")))
JSON.parse(File.read(File.join(ROOT, "data/rules/rule-set.schema.json")))

monitoring_baseline_path = "data/official-sources/monitoring-baselines.yaml"
if File.exist?(File.join(ROOT, monitoring_baseline_path))
  JSON.parse(File.read(File.join(ROOT, "data/official-sources/monitoring-baseline.schema.json")))
  monitoring_baselines = load_yaml(monitoring_baseline_path)
  monitored_source_ids = monitoring_baselines.fetch("baselines").map { |baseline| baseline.fetch("source_id") }
  registry_by_id = registry.fetch("sources").to_h { |source| [source.fetch("id"), source] }
  expected_student_pass_v1_sources = %w[
    MY-EMGS-INSURANCE-2026
    MY-EMGS-MEDICAL-SCREENING
    MY-EMGS-PASSPORT-PHOTO-GUIDELINES
    MY-EMGS-SEV-REQUIRED-COUNTRIES
    MY-EMGS-STUDENT-PASS-REQUIRED-DOCUMENTS
    MY-IMMIGRATION-STUDENT-PASS
    MY-IMMIGRATION-VISA-REQUIREMENTS-BY-COUNTRY
    MY-MQA-MQR-SEARCH
  ]

  assert(monitoring_baselines.fetch("schema_version") == 1, "Unexpected monitoring baseline schema version")
  assert(monitored_source_ids.uniq.length == monitored_source_ids.length, "Duplicate monitoring baseline source ID")
  assert(monitored_source_ids.sort == expected_student_pass_v1_sources.sort, "Unexpected monitored Student Pass V1 sources")

  monitoring_baselines.fetch("baselines").each do |baseline|
    source_id = baseline.fetch("source_id")
    source = registry_by_id.fetch(source_id) { raise "Unknown monitoring source #{source_id}" }
    assert(source.fetch("status") == "reviewed", "Monitoring source #{source_id} must be reviewed")
    assert(baseline.fetch("canonical_url") == source.fetch("canonical_url"), "Monitoring URL mismatch for #{source_id}")
    assert(baseline.fetch("canonical_url").start_with?("https://"), "Monitoring URL must use HTTPS for #{source_id}")
    assert(baseline.fetch("approved_hash").match?(/\A[0-9a-f]{64}\z/), "Invalid monitoring hash for #{source_id}")
    assert(baseline.fetch("git_commit_sha").match?(/\A(?:[0-9a-f]{40}|[0-9a-f]{64})\z/), "Invalid monitoring Git SHA for #{source_id}")
    assert(Array(baseline.fetch("allowed_hosts")).any?, "Missing allowed hosts for #{source_id}")
    assert(baseline.fetch("strategy_version") == 1, "Unsupported monitoring strategy for #{source_id}")
  end
end

source_ids = registry.fetch("sources").map { |source| source.fetch("id") }
requirement_ids = requirements.fetch("requirements").map { |requirement| requirement.fetch("id") }
rules = rule_set.fetch("rules")
rule_ids = rules.map { |rule| rule.fetch("id") }

assert(source_ids.uniq.length == source_ids.length, "Duplicate source ID")
assert(requirement_ids.uniq.length == requirement_ids.length, "Duplicate requirement ID")
assert(rule_ids.uniq.length == rule_ids.length, "Duplicate rule ID")
assert(rules.map { |rule| rule.fetch("priority") }.uniq.length == rules.length, "Duplicate rule priority")
assert(requirements.fetch("version") == rule_set.fetch("version"), "Requirement and rule versions differ")
assert(cases.fetch("rule_set_version") == rule_set.fetch("version"), "Case and rule versions differ")

requirements.fetch("requirements").each do |requirement|
  requirement.fetch("sources").each do |citation|
    assert(source_ids.include?(citation.fetch("source_id")), "Unknown source in #{requirement.fetch('id')}")
  end
end

rules.each do |rule|
  rule.fetch("requirement_ids").each do |id|
    assert(requirement_ids.include?(id), "Unknown requirement #{id} in #{rule.fetch('id')}")
  end
  rule.fetch("source_ids").each do |id|
    assert(source_ids.include?(id), "Unknown source #{id} in #{rule.fetch('id')}")
  end
end

datasets = {sev_dataset.fetch("dataset_id") => sev_dataset.fetch("country_codes")}
severity = {"pass" => 0, "action_required" => 1, "manual_review" => 2, "unsupported_scope" => 3}

cases.fetch("cases").each do |test_case|
  facts = merge_patch(cases.fetch("base_facts"), test_case.fetch("overrides"))
  triggered = rules.select { |rule| condition_matches?(rule.fetch("when"), facts, datasets) }
  triggered_ids = triggered.map { |rule| rule.fetch("id") }
  expected = test_case.fetch("expected")

  Array(expected["must_include"]).each do |id|
    assert(triggered_ids.include?(id), "#{test_case.fetch('id')}: expected #{id}")
  end
  Array(expected["must_not_include"]).each do |id|
    assert(!triggered_ids.include?(id), "#{test_case.fetch('id')}: did not expect #{id}")
  end
  if expected.key?("triggered_rule_ids")
    assert(triggered_ids == expected.fetch("triggered_rule_ids"), "#{test_case.fetch('id')}: unexpected findings #{triggered_ids}")
  end

  actual_outcome = if triggered.empty?
                     rule_set.fetch("default_outcome")
                   else
                     triggered.map { |rule| rule.fetch("then").fetch("outcome") }.max_by { |outcome| severity.fetch(outcome) }
                   end
  expected_outcome = expected["outcome"] || expected.fetch("default_outcome")
  assert(actual_outcome == expected_outcome, "#{test_case.fetch('id')}: expected #{expected_outcome}, got #{actual_outcome}")
end

puts "Validated #{source_ids.length} sources, #{requirement_ids.length} requirements, #{rule_ids.length} rules, and #{cases.fetch('cases').length} cases."
