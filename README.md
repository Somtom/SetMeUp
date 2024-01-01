# SetMeUp

SetMeUp is an open-source automation tool for system setup, inspired by Terraform. It simplifies the process of configuring a new machine or environment according to predefined specifications. SetMeUp uses YAML files for configuration, providing a readable and maintainable way of defining setup steps. It operates primarily through two commands: `plan` for generating an execution plan, and `apply` for executing this plan.

## Introduction

Welcome to SetMeUp, where onboarding headaches meet their match! Imagine a world where setting up a new developer's workstation is as simple as running a couple of commands, no more manual installation marathons or "whoops, I forgot that tool" moments. SetMeUp empowers teams to automate the nitty-gritty of tech setups, transforming hours of setup into minutes of seamless automation. With a Terraform-like approach, it uses easy-to-write YAML files, turning complex installations into a breezy, error-free process. It's more than a tool; it's your onboarding superhero, ensuring every new team member starts on the right foot, tech-wise! 🚀🖥️

Here's a list of key benefits SetMeUp offers:

- **Streamlined Onboarding**: Quickly get new team members up and running with standardized setups.
- **Error Reduction**: Minimize human error in manual setups.
- **Time Savings**: Reduce the time spent on setting up environments from hours to minutes.
- **Version Control for Setups**: Track and manage changes to setup configurations, ensuring consistency across environments.
- **Automation**: Transform repetitive, manual tasks into automated ones.
- **Consistency**: Ensure uniformity across different machines and setups.

These benefits collectively enhance the efficiency and reliability of tech onboarding and environment setups.

## Creating a Configuration File

The configuration file in YAML format is the heart of SetMeUp. It defines all the necessary steps and environment variables needed for the setup. It has 3 root properties that can be specified:

```yaml
inherits:
    - basic_setup.yaml

env_vars:
    - name: "API_KEY"
      description: "API key for external service"
      store_in: "~/.zshrc"

steps:
    - script: "scripts/install_dependencies.sh"
      description: "Install required software"
      completion_check: "which some_software"
  ```

- **`inherits`**: A list of other setmeup config yaml files that should be inherited. When providing files, the `env_vars` and `steps` will be inherited.
- **`env_vars`**: A list of environment variables that can be used or stored within the script (more details below)
- **`steps`**: A list of steps that should be executed (more details below)

### Environment Variables (`env_vars`):

Environment variables can be used for user input during `apply` or to provide specific environment variables and store them in the users shell profile or other files.

Properties that can be specified for environment variable entries

- `name`: The name of the environment variable.
- `value`: (Optional) Pre-set the variable's value.
- `store_in`: (Optional) File path where the variable should be exported.

  *Example*:

  ```yaml
  env_vars:
    - name: "API_KEY"
      description: "API key for external service"
      store_in: "~/.zshrc"
    - name: "ANSWER_TO_EVERYTHING"
      description: "A specific setting for all folks in the company"
      value: 49
      store_in: "~/.zshrc"
  ```

### Steps

We can define multiple types of steps which can have different properties:

#### Script Step

Can be used to execute an arbitrary shell command or script.

Properties:

- `script`: Specify a shell command or a script file path.
- `description`: A brief explanation of what the script does.
- `completion_check`: (Optional) A command to verify if the step has been completed. Useful for idempotent setups.
- `env_vars`: A list of environment variables required for the step. The user will only be prompted if no value is set and the step will be executed.

*Example*:

```yaml
steps:
  - script: "scripts/install_dependencies.sh"
    description: "Install required software"
    completion_check: "which some_software"
    env_vars:
      - name: "ENV_VAR"
        description: "An environment variable required for the step"
```

#### Brewfile Steps

Can be used to install a specified Brewfile

Properties:

- `brewfile`: Path to a Brewfile, which specifies Homebrew packages to install.
- `description`: Description of the Brewfile step.
- `env_vars`: A list of environment variables required for the step. The user will only be prompted if no value is set and the step will be executed.

*Example*:

```yaml
steps:
  - brewfile: "Brewfile"
    description: "Install packages from Brewfile"
```

## Generating a Plan

To generate a plan, use the `plan` command with your configuration file. This command analyzes your YAML configuration and prepares an actionable plan.

*Command*:

```bash
setmeup plan your_config_file.yaml --plan <optional-custom-name-for-plan-file.yaml>
```

The generated plan will be saved to a file (default or specified by `--plan`), which outlines the steps to be executed.

## Applying a Plan

After generating a plan, you can apply it using the `apply` command. This command will execute each step in the plan, effectively setting up your system as defined in the YAML configuration. In case you want to point it to a custom plan, you can use the `--plan` flag.

*Command*:

```bash
setmeup apply --plan your_plan_file.yaml
```

During the apply phase, SetMeUp will prompt for any required environment variables not already set and proceed to execute the setup steps.

## Contributing

(Optional) Create a virtual environment for SetMeUp:

```bash
pyenv virtualenv 3.12.0 setmeup
pyenv activate setmeup
```

Install SetMeUp locally by running:

```bash
pip install -e .
```
