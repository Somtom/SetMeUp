import argparse
from setmeup.config import YamlConfig
from setmeup.plan import Plan, DEFAULT_PLAN_FILE_NAME


def handle_plan_command(config_file, plan_file):
    config = YamlConfig(config_file)
    plan = config.plan()

    plan.visualize()
    filename = plan.save_to_file(plan_file)
    return filename


def handle_apply_command(plan_file):
    plan = Plan.load_from_file(plan_file)
    plan.apply()


def main():
    parser = argparse.ArgumentParser(
        description='SetMeUp Tool: Automate your system setup with YAML configurations.',
        epilog='Example: setmeup plan -c config.yaml -p plan.yaml'
    )
    subparsers = parser.add_subparsers(dest='command', help='Subcommands (plan/apply)')

    # Plan command
    plan_parser = subparsers.add_parser('plan', help='Generate a plan from a YAML configuration file.')
    plan_parser.add_argument('config', help='Path to the YAML configuration file.')
    plan_parser.add_argument('-p', '--plan', default=DEFAULT_PLAN_FILE_NAME, help='Path to save the generated plan file.')

    # Apply command
    apply_parser = subparsers.add_parser('apply', help='Execute steps from a plan file.')
    apply_parser.add_argument('--plan', default=DEFAULT_PLAN_FILE_NAME, help='Path to the plan file')

    args, unknown = parser.parse_known_args()

    if not hasattr(args, 'command') or args.command is None:
        parser.print_help()
        return

    if args.command == 'plan':
        plan_file = handle_plan_command(args.config, args.plan)

        # Prompt the user to apply the plan immediately
        apply_now = input("❓ Do you want to apply the plan now? (yes/no): ").strip().lower()
        if apply_now in ['yes', 'y']:
            handle_apply_command(plan_file)

    if args.command == 'apply':
        handle_apply_command(args.plan)

if __name__ == '__main__':
    main()
