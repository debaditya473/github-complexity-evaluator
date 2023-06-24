import requests
from bs4 import BeautifulSoup

username = 'debaditya473'
# url = 'https://github.com/{}'.format(username)
url = f"https://github.com/{username}?tab=repositories"

r = requests.get(url)
if r.status_code != 200:
    print("Error with username")
    exit()

soup = BeautifulSoup(r.text, 'html.parser')

repo_tags = soup.find_all('a', {'class': 'text-bold flex-auto min-width-0'})
repos = soup.find_all('div', class_ = "d-inline-block mb-1")

base_url = "https://github.com/"

for num,repo in enumerate(repos):
    for a in repo.find_all('a'):
        new_url = base_url+a["href"] 
    print(num, repo.text.strip(), new_url)

# repo_tags2 = []
# for x in repo_tags:
#   repo_tags2.append(x.find_all('span')[0]['title'])

# repo_tags2