from github import Github
from github import Auth
import yaml
import openai
import json
import requests
import tiktoken
import time

class GithubPipeline():
    def __init__(
            self,
            user : str,
            keys: dict()
        ) -> None:
        
        self.user = user
        self.keys = keys
        openai.api_key = self.keys['openai_key']
        pass

    def get_repository_data(
            self,
        ) -> dict:
        
        access_token = self.keys['github_token']
        auth = Auth.Token(access_token)
        g = Github(auth=auth)

        user = g.get_user(self.user)
        repo_file_mapping = dict()

        for repo in user.get_repos():
            # get all top-level contents of a repository
            contents = repo.get_contents("")
            repo_file_mapping[repo.name] = []

            # Breadth first Search to get all repository contents within directories
            while contents:
                file_content = contents.pop(0)
                if file_content.type == "dir":
                    contents.extend(repo.get_contents(file_content.path))
                else:
                    repo_file_mapping[repo.name].append(file_content)
        
        
        return repo_file_mapping
        # preprocessing all files

        pass

    def pipeline(self):
        repo_file_mapping = self.get_repository_data()

        best_repo = ""
        highest_score = 0
        justification = ""
        
        for key in repo_file_mapping.keys():
            # preprocessing
            repo_file_mapping[key] = self.preprocess(repo_file_mapping[key])
            
            # extracting code
            repo_file_mapping[key] = self.extract_code(repo_file_mapping[key])

            # rating with openAI
            print(key)
            repo_score, justifi = self.openAI_scoring(repo_file_mapping[key])
            print(repo_score)
            print()
            if repo_score > highest_score:
                highest_score = repo_score
                best_repo = key
                justification = justifi
        
        justification = self.summarise(justification)

        return best_repo, justification
    
    def summarise(self, payload):
        prompt_start = "Summarise the following and make it more coherent: \n"

        prompt = prompt_start + payload
        
        try:
            result = self.open_ai_request_send(prompt)
        except (openai.error.RateLimitError, openai.error.APIError) as e:
            time.sleep(60)
            result = self.open_ai_request_send(prompt)

        return result
        
    def preprocess(self, files):
        with open("allowlist.yml", 'r') as f:
            lis = yaml.safe_load(f)
        
        new_list = []
        for item in files:
            for allowword in lis:
                if item.name.endswith(allowword):
                    new_list.append(item)
        
        return new_list
        
        # with open("stoplist.yml", 'r') as f:
        #     lis = yaml.safe_load(f)
        
        # new_list = []
        # for item in files:
        #     flag = False
        #     for stopword in lis:
        #         if stopword in item.name:
        #             flag = True
        #             break
        #         pass
        #     if not flag:
        #         new_list.append(item)

        # return new_list
    
    def ipynb_preproc(self, text):
        code = ''
        json_object = json.loads(text)
        for line in json_object['cells']:
            if line['cell_type'] == 'code':
                code += '\n' + '\n'.join(line['source'])
        
        return code

    def extract_code(self, files):
        new_list = []
        for file in files:
            r = requests.get(file.download_url)
            if r.status_code != 200:
                continue
            if '.ipynb' in file.name:
                code = self.ipynb_preproc(r.text)
            else:
                code = r.text
            new_list.append(code)
        
        return new_list

    
    def openAI_scoring(self, repo_files):

        if len(repo_files) == 0:
            return 0, ''
        
        file_sizes = []
        encoding = tiktoken.encoding_for_model("gpt-3.5-turbo-16k")
        for file in repo_files:
            file_sizes.append(len(encoding.encode(file)))
        
        # payloads per minute: 13k*3
        # per minute request limit = 40k tokens, 3 requests
        
        res = []
        justifications = []
        current_files = []
        current_size = 0
        i = 1
        limit = 13000
        # time.sleep(60)
        for num, file in enumerate(repo_files):
            # ignore very big files
            if file_sizes[num] > limit:
                continue

            if current_size + file_sizes[num] > limit:
                payload = self.create_payload(current_files)
                out = self.ask_open_ai(payload)
                res.append(out)
                justification = self.justify(payload)
                justifications.append(justification)

                current_size = 0
                current_files = []
                i+=1
                r = i%3
                if r == 1:
                    time.sleep(60)
                continue
            
            current_files.append(file)
            current_size += file_sizes[num]
        
        # remaining files that havent been asked about yet
        if len(current_files) > 0:
            payload = self.create_payload(current_files)
            out = self.ask_open_ai(payload)
            res.append(out)

        
        return sum(res)/len(res), '\n'.join(justifications)
    
    def create_payload(self, files):
        str = ''
        for i, file in enumerate(files):
            str += f'\n\nCode File:\n' + file

        return str
    
    def justify(self, payload):
        prompt_start = '''
        You will be given code from a repository. Evaluate the quality of the code in the repository based on metrics like Code organisation, Abstraction, modularity, Algorithmic complexity.
        '''
        prompt_end = '''\n\nJustify your evaluation. Be brief.'''

        prompt = prompt_start + payload + prompt_end
        
        try:
            result = self.open_ai_request_send(prompt)
        except (openai.error.RateLimitError, openai.error.APIError) as e:
            time.sleep(60)
            result = self.open_ai_request_send(prompt)

        return result
    
    def ask_open_ai(self, payload):
        prompt_start = '''
        You will be given code from a repository.
Evaluate the quality of the code in the repository based on metrics like Code organisation, Abstraction, modularity, Algorithmic complexity.
        '''
        prompt_end = '''\n\nGive an overall score between 0 to 100 based on earlier metrics.
IMPORTANT: GIVE ONLY THE SCORE AND SAY NOTHING ELSE!'''

        prompt = prompt_start + payload + prompt_end
        
        try:
            result = self.open_ai_request_send(prompt)
        except (openai.error.RateLimitError, openai.error.APIError) as e:
            time.sleep(60)
            result = self.open_ai_request_send(prompt)

        return int(result)
            
    
    def open_ai_request_send(self, prompt):
        MODEL = "gpt-3.5-turbo-16k"
        response = openai.ChatCompletion.create(
            model=MODEL,
            messages=[
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )

        result = response['choices'][0]['message']['content']
    
        return result
        


if __name__ == "__main__":
    # getting API Keys
    with open("keys.yml", 'r') as f:
        keys = yaml.safe_load(f)

    openai.api_key = keys['openai_key']

    url = 'https://raw.githubusercontent.com/debaditya473/rag-qna/main/QnAModel.py'
    testtext = requests.get(url).text

    prompt_start = '''
        You will be given code from a repository.
Evaluate the quality of the code in the repository based on the Code organisation, Abstraction and modularity, Algorithmic complexity and Creativity.
        '''

    prompt_end = '''Give an overall score from 0 to 100.
IMPORTANT: GIVE ONLY THE SCORE AND SAY NOTHING ELSE! '''

    prompt = prompt_start + "File 1: \n" + testtext + "\n" + prompt_end

    MODEL = "gpt-3.5-turbo-16k"
    response = openai.ChatCompletion.create(
        model=MODEL,
        messages=[
            {"role": "user", "content": prompt},
        ],
        temperature=0,
    )

    print(response['choices'][0]['message']['content'])