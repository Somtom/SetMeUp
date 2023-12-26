import logging
import os
import yaml
import hashlib
import subprocess
from datetime import datetime
from typing import List, Set, Union
from textwrap import dedent

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


ENV_VARS_KEY = 'env_vars'
STEPS_KEY = 'steps'
INHERITS_KEY = 'inherits'
DEFAULT_PLAN_FILE_NAME = 'setmeup_plan.yaml'
DEFAULT_STATE_FILE = '~/.setmeup.state.yaml'
BREWFILE_KEY = 'brewfile'
SCRIPT_KEY = 'script'

STEP_EXECUTION_KEY = 'execute'
STEP_CHECKSUM_KEY = 'checksum'
STEP_NAME_KEY = 'name'
STEP_DESCRIPTION_KEY = 'description'
STEP_VALIDATION_KEY = 'validation'

CHECKSUM_VALUE_KEY = 'value'
CHECKSUM_ORIGIN_KEY = 'origin'
CHECKSUM_TYPE_KEY = 'type'
CHECKSUM_TYPE_FILE = 'file'
CHECKSUM_TYPE_STRING = 'string'

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
    completion_check: str
    _checksum: str
    _skip: bool
    _type: str = None

    def __init__(self, description: str = None, completion_check: str = None, skip=False) -> None:
        self.description = description
        self.completion_check = completion_check
        self._skip = skip
        self._checksum = self.checksum()
    
    def checksum(self):
        raise NotImplementedError
    
    def to_plan_format_v1(self):
        raise NotImplementedError

def checksum_from_file(file_path: str) -> str:
    # Read file content
    try:
        with open(file_path, 'r') as file:
            content = file.read()
    except FileNotFoundError:
        raise Exception(f"File '{file_path}' not found")

    # Generate SHA256 checksum
    sha256 = hashlib.sha256(content.encode('utf-8')).hexdigest()
    return sha256


def checksum_from_string(string: str) -> str:
    return hashlib.sha256(string.encode('utf-8')).hexdigest()

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
        return {
            STEP_NAME_KEY: self.name,
            STEP_DESCRIPTION_KEY: self.description,
            STEP_CHECKSUM_KEY: {
                CHECKSUM_VALUE_KEY: self._checksum,
                CHECKSUM_ORIGIN_KEY: self.brewfile,
                CHECKSUM_TYPE_KEY: CHECKSUM_TYPE_FILE,
            },
            STEP_EXECUTION_KEY: f'brew bundle --file {self.brewfile} --no-lock' ,
            STEP_VALIDATION_KEY: f'brew bundle check --file {self.brewfile}',
        }

    
# TODO: Add a check if installed attribute (a script or comand that can be executed to check whether it is installed already)
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
        return checksum_from_string(script_content)
    
    def to_plan_format_v1(self):
        if self.script_is_file:
            execute_command = f'/bin/bash {self.script}'
            checksum_type = CHECKSUM_TYPE_FILE
        else:
            execute_command = self.script
            checksum_type = CHECKSUM_TYPE_STRING
        
        return {
            STEP_NAME_KEY: self.name,
            STEP_DESCRIPTION_KEY: self.description,
            STEP_CHECKSUM_KEY: {
                CHECKSUM_VALUE_KEY: self._checksum,
                CHECKSUM_ORIGIN_KEY: self.script,
                CHECKSUM_TYPE_KEY: checksum_type,
            },
            STEP_EXECUTION_KEY: execute_command,
            STEP_VALIDATION_KEY: self.completion_check,
        }

def test_if_checksums_equal(origin: str, checksum_type: str, checksum_value: str) -> bool:
    if checksum_type == CHECKSUM_TYPE_FILE:
        return checksum_from_file(origin) == checksum_value
    elif checksum_type == CHECKSUM_TYPE_STRING:
        return checksum_from_string(origin) == checksum_value
    else:
        raise NotImplementedError(f'Cannot handle checksum type {checksum_type}')

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
        return Plan.from_yaml_config(self)


class Plan:
    version: str = '1.0'
    required_env_vars: List[dict]
    steps_to_execute: List[dict]
    _filename: str

    def __init__(
            self, 
            version: str = None,
            required_env_vars: List[dict] = None, 
            steps_to_execute: List[dict] = None,
            filename: str = None
        ) -> None:
        if version:
            self.version = version
        self.required_env_vars = required_env_vars or []
        self.steps_to_execute = steps_to_execute or []
        self._filename = filename
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
            version=plan['version'],
            required_env_vars=plan['required_env_vars'],
            steps_to_execute=plan['steps_to_execute'],
            filename=filename
        )
    
    def visualize(self):
        env_vars_string = '\n'.join(f"👉 {var['env_variable']}" for var in self.required_env_vars)
        steps_to_execute_string = '\n'.join([f"👉 Run {step[STEP_EXECUTION_KEY]}" for step in self.steps_to_execute])

        msg = dedent("""
        🚧 Execution Plan 🚧
                     
        ## You will be prompted to provide the following ENV vars
                     
        {env_vars}

        ## The following steps will be executed
                     
        {steps_to_execute}
        """)

        res = msg.format(
            steps_to_execute=steps_to_execute_string,
            env_vars=env_vars_string
        )

        self.logger.info(res)
        return res

    def apply(self):
        def check_if_step_ran(step: dict) -> Union[dict, None]:
            completed = None
            if step.get(STEP_VALIDATION_KEY):
                completed = subprocess.call(step[STEP_VALIDATION_KEY], shell=True) == 0
            return completed

        # Pre checks
        for step in self.steps_to_execute:
            # Check whether checksums are still the same (i.e. did any file content change?)
            checksum_data = step[STEP_CHECKSUM_KEY]            
            checksum_equal = test_if_checksums_equal(
                origin=checksum_data[CHECKSUM_ORIGIN_KEY], 
                checksum_type=checksum_data[CHECKSUM_TYPE_KEY], 
                checksum_value=checksum_data[CHECKSUM_VALUE_KEY]
            )
            if not checksum_equal:
                self.logger.warning(f"😱 Checksums for step {step[STEP_NAME_KEY]} changed. You need to re-run the plan command.")
                return 
            
        # Set required environment variables
        for env_var in self.required_env_vars:
            user_input = input(f"Enter {env_var['name']} ({env_var['description']}): ")
            os.environ[env_var['env_variable']] = user_input
            if 'store_in' in env_var and env_var['store_in']:
                with open(env_var['store_in'], 'a') as file:
                    file.write(f'\nexport {env_var["env_variable"]}="{user_input}"')
        
        # Execute steps
        for step in self.steps_to_execute:
            if check_if_step_ran(step):
                self.logger.info(f'✅ Skipping step {step[STEP_EXECUTION_KEY]} since it already ran')
                continue

            try:
                self.logger.info(f'⚪️ Executing Step: {step[STEP_EXECUTION_KEY]}')
                subprocess.run([step[STEP_EXECUTION_KEY]], check=True, shell=True)
            except subprocess.CalledProcessError as e:
                self.logger.error(f"🔥🔥🔥 Step {step['name']} failed 🔥🔥🔥")
                self.logger.error(e)
                break
            
            validation_passed = check_if_step_ran(step)
            if validation_passed is None:
                self.logger.info(f"🟢 Step {step[STEP_NAME_KEY]} completed but could not verify")
            elif validation_passed:
                self.logger.info(f"✅ Step {step[STEP_NAME_KEY]} completed")
            else:
                self.logger.error(f"🔴 Step {step[STEP_NAME_KEY]} not completed successfully")
            step['executed_at'] = datetime.now()
        self.save_to_file(filename=self._filename)


    def save_to_file(self, filename: str = DEFAULT_PLAN_FILE_NAME):
        plan = {
            'version': self.version,
            'generated_at': datetime.now().isoformat(),
            'required_env_vars': self.required_env_vars,
            'steps_to_execute':self.steps_to_execute,
        }

        with open(filename, 'w') as file:
            yaml.dump(plan, file, default_flow_style=False)

        # Store latest filename information
        self._filename = filename
    
