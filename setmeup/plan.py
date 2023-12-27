from setmeup.utils import check_if_step_ran, checksum_from_file, checksum_from_string
import logging
import os
import yaml
import subprocess
from datetime import datetime
from typing import List
from textwrap import dedent

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


DEFAULT_PLAN_FILE_NAME = 'setmeup_plan.yaml'

class PlanEnvironmentVariable:
    name: str 
    description: str
    name: str 
    store_in: str
    value: str

    def __init__(
            self, 
            name: str, 
            store_in: str,
            value: str,
            description: str = '', 
        ) -> None:
        self.name = name 
        self.description = description
        self.store_in = store_in
        self.value = value
        self.logger = logging.getLogger(__name__)

    def to_dict(self):
        return {
            'name': self.name,
            'description': self.description,
            'store_in': self.store_in,
            'value': self.value
        }

    def set_value(self, value):
        if os.environ.get(self.name):
            self.logger.info(f'✅ Env variable {self.name} already set in environment')
            return
        os.environ[self.name] = value
        self.logger.info(f'✅ Set env variable {self.name} in environment')


    def store_value(self, value):
        env_var_set_string = f'{self.name}="{value}"'
        file_updated = False

        if self.store_in:
            file_path = os.path.expanduser(self.store_in)
            lines = []
            if os.path.isfile(file_path):
                # Read the file and store the lines
                with open(file_path, 'r') as file:
                    lines = file.readlines()
            # Check and update the environment variable
            with open(file_path, 'w+') as file:
                for line in lines:
                    if line.strip().startswith(f'export {self.name}='):
                        # Update the existing variable
                        file.write(f'export {env_var_set_string}\n')
                        file_updated = True
                        self.logger.info(f'✅ Updated existing env variable {self.name} to {self.store_in}')
                    else:
                        # Write the line as it is
                        file.write(line)

                # If the variable was not found, append it
                if not file_updated:
                    file.write(f'\nexport {env_var_set_string}\n')
                    self.logger.info(f'✅ Wrote env variable {self.name} to {self.store_in}')


class PlanStepChechsum:
    value: str
    origin: str 
    checksum_type: str

    TYPE_STRING = 'string'
    TYPE_FILE = 'file'

    def __init__(self, value: str, origin: str, checksum_type: str) -> None:
        self.value = value 
        self.origin = origin
        self.checksum_type = checksum_type
    
    def to_dict(self):
        return {
            'value': self.value,
            'origin': self.origin,
            'checksum_type': self.checksum_type,
        }
    
    def test_if_checksums_equal(self, checksum_value):
        if self.checksum_type == PlanStepChechsum.TYPE_FILE:
            return checksum_from_file(self.origin) == checksum_value
        elif self.checksum_type == PlanStepChechsum.TYPE_STRING:
            return checksum_from_string(self.origin) == checksum_value
        else:
            raise NotImplementedError(f'Cannot handle checksum type {self.checksum_type}')
   

class PlanStep:
    name: str
    description: str
    checksum: PlanStepChechsum
    execute: str
    validation: str
    executed_at: datetime
    skip: bool

    def __init__(
            self, 
            name: str, 
            description: str, 
            checksum: dict,
            execute: str,
            validation: str, 
            executed_at: datetime = None,
            skip: bool = False
        ) -> None:
        self.name = name
        self.description = description
        self.checksum = PlanStepChechsum(**checksum)
        self.execute = execute
        self.validation = validation
        self.executed_at = executed_at
        self.skip = skip or False

    def to_dict(self):
        return {
            'name': self.name,
            'description': self.description,
            'checksum': self.checksum.to_dict(),
            'execute': self.execute,
            'validation': self.validation,
            'skip': self.skip
        }
    
    @property
    def plan_string(self):
        if self.skip:
            return f"⏩ {self.description}:\n  [SKIP] {self.execute}" 
        else:
            return f"👉 {self.description}:\n  [RUN] {self.execute}" 
    
    def check_if_ran(self):
        return check_if_step_ran(self.validation)

    def run(self):
        subprocess.run([self.execute], check=True, shell=True)


class Plan:
    setmeup_version: str = '1.0'
    required_env_vars: List[PlanEnvironmentVariable]
    steps_to_execute: List[PlanStep]
    _filename: str

    def __init__(
            self, 
            setmeup_version: str = None,
            required_env_vars: List[dict] = None, 
            steps_to_execute: List[PlanStep] = None,
            filename: str = None
        ) -> None:
        if setmeup_version:
            self.setmeup_version = setmeup_version
        self.required_env_vars = required_env_vars or []
        self.steps_to_execute = steps_to_execute or []
        self._filename = filename
        self.logger = logging.getLogger(__name__)

    def __repr__(self) -> str:
        return self.visualize()

    @classmethod
    def load_from_file(cls, filename: str = DEFAULT_PLAN_FILE_NAME):
        with open(filename, 'r') as file:
            plan = yaml.safe_load(file)

        return cls(
            setmeup_version=plan['setmeup_version'],
            required_env_vars=[PlanEnvironmentVariable(**var) for var in plan['required_env_vars']],
            steps_to_execute=[PlanStep(**step) for step in plan['steps_to_execute']],
            filename=filename
        )
    
    def visualize(self):
        env_vars_string = '\n'.join(f"👉 {var.name} will be stored in {var.store_in}" for var in self.required_env_vars if var.store_in)
        steps_to_execute = []
        skipped_steps = []
        for step in self.steps_to_execute:
            if step.skip:
                skipped_steps.append(step.plan_string)
            else:
                steps_to_execute.append(step.plan_string)

        msg = dedent("""
        🚧 Execution Plan 🚧
                     
        ## The following env variables will be stored
                     
        {env_vars}

        ## The following steps will be executed
                     
        {steps_to_execute}
                     
        ## The following steps will be skipped
                     
        {skipped_steps}
        """)

        res = msg.format(
            steps_to_execute='\n'.join(steps_to_execute),
            skipped_steps='\n'.join(skipped_steps),
            env_vars=env_vars_string
        )

        self.logger.info(res)
        return res

    def apply(self) -> None:

        # Pre checks
        for step in self.steps_to_execute:
            # Check whether checksums are still the same (i.e. did any file content change?)
            checksum_data: PlanStepChechsum = step.checksum   
            checksum_equal = checksum_data.test_if_checksums_equal(checksum_data.value) 
            if not checksum_equal:
                self.logger.warning(f"😱 Checksums for step {step.name} changed. You need to re-run the plan command.")
                return 
            
        # Set required environment variables
        for env_var in self.required_env_vars:
            value = env_var.value
            if value is None:
                value = input(f"Enter a value for {env_var.name} ({env_var.description}): ")
            env_var.set_value(value)
            env_var.store_value(value)

        # Execute steps
        for step in self.steps_to_execute:
            if step.check_if_ran():
                self.logger.info(f'✅ Skipping step {step.name} since it already ran')
                continue

            try:
                self.logger.info(f'⚪️ Executing Step: {step.name}')
                step.run()
            except subprocess.CalledProcessError as e:
                self.logger.error(f"🔥🔥🔥 Step {step.name} failed 🔥🔥🔥")
                self.logger.error(e)
                break
            
            validation_passed = step.check_if_ran()
            if validation_passed is None:
                self.logger.info(f"🟢 Step {step.name} completed but could not verify")
            elif validation_passed:
                self.logger.info(f"✅ Step {step.name} completed")
            else:
                self.logger.error(f"🔴 Step {step.name} not completed successfully")
            step.executed_at = datetime.now()
        self.save_to_file(filename=self._filename)


    def save_to_file(self, filename: str = DEFAULT_PLAN_FILE_NAME) -> str:
        plan = {
            'setmeup_version': self.setmeup_version,
            'generated_at': datetime.now().isoformat(),
            'required_env_vars': [var.to_dict() for var in self.required_env_vars],
            'steps_to_execute':[step.to_dict() for step in self.steps_to_execute],
        }

        with open(filename, 'w') as file:
            yaml.dump(plan, file, default_flow_style=False)

        # Store latest filename information
        self._filename = filename

        return filename
