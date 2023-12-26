import argparse
from setmeup.plan import handle_plan_command
from setmeup.apply import handle_apply_command
from setmeup.utils import DEFAULT_PLAN_FILE_NAME


def main():
    parser = argparse.ArgumentParser(description='SetMeUp Tool')
    subparsers = parser.add_subparsers(dest='command')

    # Plan command
    plan_parser = subparsers.add_parser('plan', help='Generate plan from YAML config')
    plan_parser.add_argument('config', help='Path to the YAML configuration file.')
    plan_parser.add_argument('-p', '--plan', default=DEFAULT_PLAN_FILE_NAME, help='Path to save the generated plan file.')
    
    # Apply command
    apply_parser = subparsers.add_parser('apply', help='Apply a plan')
    apply_parser.add_argument('--plan', default=DEFAULT_PLAN_FILE_NAME, help='Path to the plan file')

    args = parser.parse_args()

    if args.command == 'plan':
        handle_plan_command(args.config, args.plan)
    
    if args.command == 'apply':
        handle_apply_command(args.plan)

if __name__ == '__main__':
    main()
