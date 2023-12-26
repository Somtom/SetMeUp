from setmeup.utils import YamlConfig, Plan

def handle_plan_command(config_file, plan_file):
    config = YamlConfig(config_file)
    plan = Plan.from_yaml_config(config)

    plan.visualize()
    plan.save_to_file(plan_file)
