from setmeup.utils import Plan

def handle_apply_command(plan_file):
    plan = Plan.load_from_file(plan_file)
    plan.apply()
