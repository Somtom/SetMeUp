import logging
import os
import yaml
from typing import List, Set
from setmeup.utils import check_if_step_ran, checksum_from_file, checksum_from_string, get_file_content_or_command, is_file
from setmeup.plan import Plan, PlanStep, PlanStepChechsum, PlanEnvironmentVariable

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

ENV_VARS_KEY = 'env_vars'
INHERITS_KEY = 'inherits'
BREWFILE_KEY = 'brewfile'
SCRIPT_KEY = 'script'


class EnvironmentVariable:
    name: str 
    description: str
    name: str 
    store_in: str

    def __init__(
            self, 
            name: str, 
            value: str = None,
            store_in: str = None,
            description: str = '', 
        ) -> None:
        self.description = description
        self.name = name 
        self.store_in = store_in
        self.value = value

    def __hash__(self) -> int:
        return int(hash(self.name))
    
    def to_plan_format_v1(self):
        return PlanEnvironmentVariable(
            description=self.description,
            name=self.name,
            store_in=self.store_in,
            value=self.value,
        )
    
class SetupStep:
    name: str
    description: str 
    completion_check: str
    _checksum: str
    _type: str = None

    def __init__(self, description: str = None, completion_check: str = None) -> None:
        self.description = description
        self.completion_check = completion_check
        self._checksum = self.checksum()
    
    def checksum(self):
        raise NotImplementedError
    
    def to_plan_format_v1(self):
        raise NotImplementedError
    

class BrewfileSetupStep(SetupStep):
    brewfile: str 
    name = 'Install Brew Bundle'
    _type = 'brewfile'

    def __init__(self, brewfile: str, *args, **kwargs) -> None:
        self.brewfile = brewfile
        super().__init__(*args, **kwargs)

    def checksum(self) -> str:
        return checksum_from_file(self.brewfile)

    def to_plan_format_v1(self):
        validation_command = f'brew bundle check --file {self.brewfile}'
        return PlanStep(
            name=self.name,
            description=self.description,
            checksum={
                'value': self._checksum, 
                'origin': self.brewfile, 
                'checksum_type': PlanStepChechsum.TYPE_FILE
            },
            execute=f'brew bundle --file {self.brewfile} --no-lock',
            validation=validation_command,
            skip=check_if_step_ran(validation_command)
        )

    
class ScriptSetupStep(SetupStep):
    script: str 
    _type = 'script'

    def __init__(
        self, 
        script: str, 
        *args, 
        **kwargs
    ) -> None:
        self.script = script
        self.name = f'Execute Script {script}'
        super().__init__(*args, **kwargs)

    def get_script_content(self) -> str:
        return get_file_content_or_command(self.script)

    def checksum(self) -> str:
        script_content = self.get_script_content()
        # Generate SHA256 checksum
        return checksum_from_string(script_content)
    
    def to_plan_format_v1(self):
        if is_file(self.script):
            execute_command = f'/bin/bash {self.script}'
            checksum_type = PlanStepChechsum.TYPE_FILE
        else:
            execute_command = self.script
            checksum_type = PlanStepChechsum.TYPE_STRING

        validation_command = f'/bin/bash {self.completion_check}' if is_file(self.completion_check) else self.completion_check

        return PlanStep(
            name=self.name,
            description=self.description,
            checksum={
                'value': self._checksum, 
                'origin': self.script, 
                'checksum_type': checksum_type
            },
            execute=execute_command,
            validation=validation_command,
            skip=check_if_step_ran(validation_command)
        )
        

class YamlConfig:
    inherits: List['YamlConfig']
    env_vars: Set[EnvironmentVariable]
    steps: List[SetupStep]

    def __init__(self, filepath):
        self.filepath = filepath
        self.load_yaml()

    def load_yaml(self):
        with open(self.filepath, 'r') as file:
            config = yaml.safe_load(file)
        self.inherits = config.get(INHERITS_KEY, [])
        self.env_vars = {EnvironmentVariable(**var) for var in config.get(ENV_VARS_KEY, [])}
        self.steps = self.parse_steps(config)
        self.parse_inherited_configs()

    def parse_steps(self, config) -> List[SetupStep]:
        steps = []
        base_path = os.path.dirname(self.filepath)  # Base directory of the YAML file

        for step in config.get('steps', []):
            if step.get(BREWFILE_KEY):
                steps.append(BrewfileSetupStep(**step))
            elif step.get(SCRIPT_KEY):
                # Check if script is a path and resolve its relative path
                script = step[SCRIPT_KEY]
                is_file = os.path.isfile(os.path.join(base_path, script))
                step[SCRIPT_KEY] = os.path.join(base_path, script) if is_file else script
                steps.append(ScriptSetupStep(**step))
        return steps

    def parse_inherited_configs(self):
        """ Recursively load inherited configurations. """
        new_env_vars = set()
        new_steps = []
        for relative_path in self.inherits:
            base_path = os.path.dirname(self.filepath)
            absolute_path = os.path.join(base_path, relative_path)

            inherited_config = YamlConfig(absolute_path)
            inherited_config.parse_inherited_configs()
            new_env_vars.update(inherited_config.env_vars)
            new_steps += inherited_config.steps
        
        # self.env_vars overwrites inherited env vars
        new_env_vars.update(self.env_vars)
        self.env_vars = new_env_vars
        # Inherited steps are performed in the order the are specified prior to self.steps
        self.steps = new_steps + self.steps

    def plan(self) -> 'Plan':
        plan = Plan()
        plan.required_env_vars = [var.to_plan_format_v1() for var in self.env_vars]
        plan.steps_to_execute = [step.to_plan_format_v1() for step in self.steps]
        return plan
