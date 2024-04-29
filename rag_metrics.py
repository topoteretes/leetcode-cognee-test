import os
from typing import Tuple, List, Any

from deepeval.benchmarks.human_eval.human_eval import HumanEval
from deepeval.benchmarks.tasks import HumanEvalTask
from deepeval.models import DeepEvalBaseLLM
from langchain_core.messages import AIMessage, HumanMessage
from langchain_openai import ChatOpenAI
import os
import glob
from dotenv import load_dotenv
load_dotenv()

class GPT4Model(DeepEvalBaseLLM):
    def __init__(self, model, context,  *args, **kwargs):
        # First, initialize the model attribute before calling super()
        self.model = model
        self.context = context
        super().__init__(*args, **kwargs)


    def load_model(self):
        return self.model

    def generate(self, prompt: str) -> str:
        chat_model = self.load_model()
        return chat_model.invoke(prompt).content

    def get_model_name(self):
        return "OpenAI Model"

    async def a_generate(self, prompt: str) -> str:
        chat_model = self.load_model()
        res = await chat_model.ainvoke(prompt)
        return res.content

    # def evaluate(self, prompt: str, context:str) -> list[str]:
    #     chat_model = self.load_model()
    #     generations = chat_model._generate([HumanMessage(prompt)]).generations
    #     completions = [r.text for r in generations]
    #     return completions


    def generate_samples(
            self, prompt: str, n: int, temperature: float
    ) -> list[Any]:
        chat_model = self.load_model()
        og_parameters = {"n": chat_model.n, "temp": chat_model.temperature}
        chat_model.n = n
        chat_model.temperature = temperature
        print("CONTEXT IS: ", self.context )
        print("PROMPT IS: ", prompt)
        generations = chat_model._generate([HumanMessage(prompt)]).generations
        completions = [r.text for r in generations]
        return completions



for i, task in enumerate(HumanEvalTask):
    print(f"Iteration {i}: {task}")
    i = i + 1

    # Get a list of all files in the directory
    files = glob.glob(f'continue_requests/request_{str(i)}.txt')

    # Sort the files by sequence number
    files.sort(key=lambda x: int(x.split('_')[-1].split('.')[0]))

    # Iterate over the files
    print("Files: ", files)
    for file_path in files:

        with open(file_path, 'r') as file:
            # Load the file
            content = file.read()

            # Process the content of the file
            print(f"Processing file: {file_path}")
            print(content)


            gpt_4 = GPT4Model(model=ChatOpenAI(model_name = "gpt-4-1106-preview", api_key= os.getenv("OPENAI_API")), context=content)

            # Define benchmark with specific tasks and number of code generations
            benchmark = HumanEval(
                tasks=[task],
                n=1,

            )

            # Replace 'gpt_4' with your own custom model
            benchmark.evaluate(model=gpt_4, k=1)
            print(benchmark.overall_score)


