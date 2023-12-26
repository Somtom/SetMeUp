import logging
import os
import yaml
import hashlib
import subprocess
from datetime import datetime
from typing import List, Set
from textwrap import dedent

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


ENV_VARS_KEY = 'env_vars'
STEPS_KEY = 'steps'
INHERITS_KEY = 'inherits'
DEFAULT_PLAN_FILE_NAME = 'setmeup_plan.yaml'
BREWFILE_KEY = 'brewfile'
SCRIPT_KEY = 'script'
EXECUTION_KEY = 'execute'

class EnvironmentVariable:
    name: str 
    description: str
    env_variable: str 
    store_in: str

    def __init__(
            self, 
            name, 
            description: str, 
            env_variable: str = None, 
            store_in: str = None
        ) -> None:
        self.name = name 
        self.description = description
        # In case no env_variable is specified, we default to the name argument
        self.env_variable = env_variable or name 
        self.store_in = store_in

    def __hash__(self) -> int:
        return int(hash(self.env_variable))
    
    def to_plan_format_v1(self):
        return {
            'name': self.name,
            'description': self.description,
            'env_variable': self.env_variable,
            'store_in': self.store_in
        }


class SetupStep:
    name: str
    description: str 
    _checksum: str
    _skip: bool
    _type: str = None

    def __init__(self, description: str = None, skip=False) -> None:
        self.description = description
        self._skip = skip
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
        # Read brewfile content
        try:
            with open(self.brewfile, 'r') as file:
                brewfile_content = file.read()
        except FileNotFoundError:
            raise Exception(f"Brewfile '{self.brewfile}' not found")

        # Generate SHA256 checksum
        sha256 = hashlib.sha256(brewfile_content.encode('utf-8')).hexdigest()
        return sha256

    def to_plan_format_v1(self):
        execute_command = f'brew bundle --file {self.brewfile} --no-lock' 
        return {
            'name': self.name,
            'description': self.description,
            'checksum': self._checksum,
            EXECUTION_KEY: execute_command
        }
    

class ScriptSetupStep(SetupStep):
    script: str 
    name = 'Execute Script'
    _type = 'script'

    def __init__(self, script: str, *args, **kwargs) -> None:
        self.script = script
        super().__init__(*args, **kwargs)

    @property
    def script_is_file(self):
        return os.path.isfile(os.path.join(self.script))

    def get_script_content(self) -> str:
        script_content = ""
        if self.script_is_file:
            # If it's a file, read its content
            try:
                with open(self.script, 'r') as file:
                    script_content = file.read()
            except FileNotFoundError:
                raise Exception(f"Script file '{self.script}' not found")
        else:
            # If it's not a file, use the script string directly
            script_content = self.script

        # Generate SHA256 checksum
        return script_content

    def checksum(self) -> str:
        script_content = self.get_script_content()
        # Generate SHA256 checksum
        return hashlib.sha256(script_content.encode('utf-8')).hexdigest()
    
    def to_plan_format_v1(self):
        execute_command = f'/bin/bash {self.script}' if self.script_is_file else f'/bin/bash -c {self.script}'
        
        return {
            'name': self.name,
            'description': self.description,
            'checksum': self._checksum,
            EXECUTION_KEY: execute_command
        }


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

    def plan(self, state_file='') -> 'Plan':
        # For now we just assume no state file
        if state_file is None:
            return Plan(self)


class Plan:
    version: str = '1.0'
    required_env_vars = List[dict]
    steps_to_execute = List[dict]

    def __init__(
            self, 
            version: str = None,
            required_env_vars: List[dict] = None, 
            steps_to_execute: List[dict] = None
        ) -> None:
        if version:
            self.version = version
        self.required_env_vars = required_env_vars or []
        self.steps_to_execute = steps_to_execute or []
        self.logger = logging.getLogger(__name__)

    def __repr__(self) -> str:
        return self.visualize()

    @classmethod
    def from_yaml_config(cls, config: YamlConfig) -> 'Plan':
        plan = cls()
        plan.required_env_vars = [var.to_plan_format_v1() for var in config.env_vars]
        plan.steps_to_execute = [step.to_plan_format_v1() for step in config.steps if not step._skip]
        return plan

    @classmethod
    def load_from_file(cls, filename: str = DEFAULT_PLAN_FILE_NAME):
        with open(filename, 'r') as file:
            plan = yaml.safe_load(file)
        return cls(
            version = plan['version'],
            required_env_vars = plan['required_env_vars'],
            steps_to_execute = plan['steps_to_execute']
        )
    
    def visualize(self):
        env_vars_string = '\n'.join(var['env_variable'] for var in self.required_env_vars)
        steps_to_execute_string = '\n'.join([f"Run {step[EXECUTION_KEY]}" for step in self.steps_to_execute])

        msg = dedent("""
        # Execution Plan
                     
        ## You will be prompted to provide the following ENV vars
        {env_vars}

        ## The following steps will be executed
        {steps_to_execute}
        """)

        return msg.format(
            steps_to_execute=steps_to_execute_string,
            env_vars=env_vars_string
        )

    def apply(self):
        # Set required environment variables
        for env_var in self.required_env_vars:
            user_input = input(f"Enter {env_var['name']} ({env_var['description']}): ")
            os.environ[env_var['env_variable']] = user_input
            if 'store_in' in env_var and env_var['store_in']:
                with open(env_var['store_in'], 'a') as file:
                    file.write(f'\nexport {env_var["env_variable"]}="{user_input}"')

        for step in self.steps_to_execute:
            self.logger.info(f'Executing Step: {step[EXECUTION_KEY]}')
            subprocess.run([step[EXECUTION_KEY]], check=True, shell=True)

    def save_to_file(self, filename: str = DEFAULT_PLAN_FILE_NAME):
        plan = {
            'version': self.version,
            'generated_at': datetime.now().isoformat(),
            'required_env_vars': self.required_env_vars,
            'steps_to_execute':self.steps_to_execute,
        }

        with open(filename, 'w') as file:
            yaml.dump(plan, file, default_flow_style=False)
    
