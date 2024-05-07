import os
import re

import pandas as pd
import requests
from datetime import datetime, timedelta

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel

load_dotenv()

# Constants
GITHUB_API = "https://api.github.com"
TOKEN = os.getenv("GITHUB_TOKEN")  # Replace this with your GitHub token
HEADERS = {'Authorization': f'token {TOKEN}'}
session = requests.Session()
session.headers.update(HEADERS)

def extract_pr_files_content(owner, repo, pull_number, session, max_files=None):
    """Extract the content of changed files from a GitHub pull request."""
    url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pull_number}/files"
    response = session.get(url, headers={'Accept': 'application/vnd.github.v3.raw'})
    response.raise_for_status()
    files = response.json()
    result = {"prediction": None, "context": {}}

    for i, file_info in enumerate(files):
        if max_files is not None and i >= max_files:
            break  # Stop iteration if maximum number of files reached
        file_url = file_info['raw_url']
        file_response = session.get(file_url)
        file_content = file_response.text

        if i == 0:
            result['prediction'] = file_content
        else:
            result['context'][file_info['filename']] = file_content

    return result

# def get_repositories(created_after="2018-01-01", stars="1000..5000", forks="100..1000", max_files=None):
#     """Fetch repositories based on the given search criteria."""
#     query = (
#         "language:python stars:1000..5000 forks:100..1000"
#         f" created:>={created_after } license:mit is:public"
#     )
#     params = {
#         'q': query,
#         'sort': 'updated',
#         'order': 'desc',
#         'per_page': 100
#     }
#     response = requests.get(f"{GITHUB_API}/search/repositories", params=params)
#     return response.json().get('items', [])
#
def get_repositories(created_after="2018-01-01", stars="1000..5000", forks="100..1000", max_files=None):
    """
    Fetches repositories based on specified search criteria with optional file count filtering.

    Args:
    created_after (str): Filter repos created after this date.
    stars (str): Range of stars the repository must have.
    forks (str): Range of forks the repository must have.
    max_files (int, optional): Maximum number of files allowed in the repository.

    Returns:
    list: A list of repositories meeting the criteria.
    """
    headers = {'Authorization': f'token {TOKEN}'}
    query = f"language:python stars:{stars} forks:{forks} created:>={created_after} license:mit is:public"
    params = {
        'q': query,
        'sort': 'updated',
        'order': 'desc',
        'per_page': 100
    }

    try:
        response = requests.get(f"{GITHUB_API}/search/repositories", headers=headers, params=params)
        response.raise_for_status()
        repositories = response.json().get('items', [])
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
        return []
    except Exception as err:
        print(f"An error occurred: {err}")
        return []

    filtered_repositories = []
    for repo in repositories:
        files_url = f"{GITHUB_API}/repos/{repo['owner']['login']}/{repo['name']}/contents"
        try:
            files_response = requests.get(files_url, headers=headers)
            files_response.raise_for_status()
            files_count = len(files_response.json())
            if max_files is None or files_count <= max_files:
                filtered_repositories.append(repo)
        except requests.exceptions.HTTPError as e:
            print(f"Error retrieving files for {repo['name']}: {e.response.status_code}")

    return filtered_repositories

def fetch_issue_comments(issue_url):
    """Fetch the initial comment of an issue from its GitHub URL."""

    # Construct the API endpoint for comments from the given issue URL
    api_endpoint = issue_url.replace('https://github.com', GITHUB_API) + '/comments'

    # Use the session with headers to make the request
    response = session.get(api_endpoint)
    if response.status_code == 200:
        comments = response.json()
        if comments and isinstance(comments, list) and comments:
            # Return the body of the first comment if available
            return comments[0]['body']
        else:
            return "No comments"
    else:
        return f"Failed to fetch comments. Status code: {response.status_code}"


def fetch_issue_data(issue_number, repo):
    """Fetch all comments/discussions on the issue and include the first comment."""
    timeline_url = f"{GITHUB_API}/repos/{repo['owner']['login']}/{repo['name']}/issues/{issue_number}/timeline"
    comments_url = f"{GITHUB_API}/repos/{repo['owner']['login']}/{repo['name']}/issues/{issue_number}/comments"

    # Use a session to make requests
    with requests.Session() as session:
        session.headers.update({'Accept': 'application/vnd.github.mockingbird-preview'})

        # Fetch the timeline and comments concurrently if possible, or sequentially
        timeline_response = session.get(timeline_url)
        comments_response = session.get(comments_url)

        timeline_data = timeline_response.json()
        comments_data = comments_response.json()
        comments_body_string = ""



        # Iterate over each comment and append its body to the result string
        for comment in comments_data:
            # print("comm is", str(comment))
            comments_body_string += comment['body'] + "\n\n"  # Add two newlines for better readability between comments

        # return comments_body_string
        return timeline_data, comments_body_string

class Question(BaseModel):
    """Answer."""
    question: str

def determine_issue_question(issue_title_body):
    import instructor
    from pydantic import BaseModel
    from typing import List, Type
    model = "gpt-4-1106-preview"
    def create_structured_output(text_input: str, system_prompt: str, response_model: Type[BaseModel]) -> BaseModel:
        """Generate a response from a user query."""

        client = instructor.from_openai(OpenAI())


        return client.chat.completions.create(
            model = model,
            messages = [
                {
                    "role": "user",
                    "content": f"""Use the given format to create a very simple question that represents this PR issue: {text_input}. """,
                },
                {"role": "system", "content": system_prompt},
            ],
            response_model = response_model,
        )

    response = create_structured_output(issue_title_body, "What is the question?", Question)

    return response

def get_last_commit_before_merge(repo_owner, repo_name, pr_number, session):
    pr_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/pulls/{pr_number}"
    pr_response = session.get(pr_url)
    pr_response.raise_for_status()
    pr_data = pr_response.json()

    if 'merge_commit_sha' in pr_data and pr_data['merged']:
        merge_commit_sha = pr_data['merge_commit_sha']
        commit_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/commits/{merge_commit_sha}"
        commit_response = session.get(commit_url)
        commit_response.raise_for_status()
        commit_data = commit_response.json()

        if 'parents' in commit_data and len(commit_data['parents']) > 0:
            return commit_data['parents'][0]['sha']  # Return the first parent commit SHA
    return None


def process_issue(issue, repo, max_files=5):
    """ Process issues and fetch associated PRs
    :param issue: Issue object
    :param repo: Repository object
    :return: DataFrame with issue data
    """
    # Fetch discussions and the first comment
    discussions, comments= fetch_issue_data(issue['number'], repo)


    # Collect PR links
    pr_links = []
    fix_prs = []
    master_commits_before_merge = {}
    discussion_context =""
    counter = 0
    first_comment = ""
    pr_files_content = {}
    for event in discussions:
        if counter == 0:
            try:
                first_comment = event['body']
                counter += 1
            except:
                pass

        if counter>0:
            try:
                discussion_context += event['body']
                counter += 1
            except:
                pass

        if event.get('event') == 'referenced' and 'commit_id' in event:
            prs = fetch_pr_from_commit(event['commit_id'], repo)
            pr_links.extend(prs)
            for pr_link in prs:
                pr_number = pr_link.split('/')[-1]
                pr_content = extract_pr_files_content(repo['owner']['login'], repo['name'], pr_number, session, max_files=max_files)
                pr_files_content[pr_link] = pr_content
                last_commit_before_merge = get_last_commit_before_merge(repo['owner']['login'], repo['name'], pr_number, session)
                if last_commit_before_merge:
                    master_commits_before_merge[pr_link] = last_commit_before_merge
        if 'body' in event:
            # Pattern to capture "Fixed by #number" or "closed this as completed in #number"
            fixed_by_prs = re.findall(r"(?:Fixed by|closed this as completed in) #(\d+)", event['body'])
            fix_prs.extend(fixed_by_prs)

        # Optionally fetch details for PRs mentioned as fixing the issue
        for pr_number in fix_prs:
            pr_link = f"https://github.com/{repo['owner']['login']}/{repo['name']}/pull/{pr_number}"
            pr_links.append(pr_link)
    # Compile issue data
    issue_data = {
        'Repository': f"{repo['owner']['login']}/{repo['name']}",
        'Issue URL': issue['html_url'],
        'Associated PRs': pr_links,
        'Issue Name': issue['title'],
        'Issue Question': str(determine_issue_question(str(issue['title']) + " " + str(issue['body'])).dict()),
        'Issue Text': issue['body'],
        'Context': str(comments),
        'PR prediction': pr_files_content,
        'PR Files Content': pr_files_content,
        'Master Branch Commits Before Merge': master_commits_before_merge
    }
    print("Master commits Data: ", master_commits_before_merge)

    return pd.DataFrame([issue_data])


def fetch_pr_from_commit(commit_id, repo):
    """ Fetch pull requests associated with a commit """
    commit_url = f"{GITHUB_API}/repos/{repo['owner']['login']}/{repo['name']}/commits/{commit_id}/pulls"
    response = requests.get(commit_url, headers={'Accept': 'application/vnd.github.groot-preview+json'})
    pull_requests = response.json()
    return [pr['html_url'] for pr in pull_requests]  # Return a list of PR links



def check_issues(repo, max_files = 5):
    all_issues_df = pd.DataFrame()  # Initialize an empty DataFrame
    issues_url = f"{GITHUB_API}/repos/{repo['owner']['login']}/{repo['name']}/issues"
    params = {'state': 'closed', 'labels': 'good first issue', 'per_page': 100, 'since': '2024-01-01T00:00:00Z'}
    response = session.get(issues_url, params=params)
    issues = response.json()

    for issue in issues:
        # print("Issue: ", issue)  # This will help you see what each 'issue' contains
        issue_df = process_issue(issue, repo, max_files=max_files)
        issue_df['Repository ID'] = repo['id']
        all_issues_df = pd.concat([all_issues_df, issue_df], ignore_index=True)
        # print(all_issues_df.head(10))



    return all_issues_df


def main(n, created_after="2018-01-01", stars="1000..5000", forks="100..1000", max_pr_files=10):
    """ Main function to fetch issues from repositories and create test set"""
    main_df = pd.DataFrame()
    rate_limit_status = requests.get('https://api.github.com/rate_limit', headers=HEADERS)
    print(rate_limit_status.json())
    repos = get_repositories(created_after=created_after, stars=stars, forks=forks)
    print(f"Found {len(repos)} repositories.")

    for i, repo in enumerate(repos):
        if i == n:
            break
        issues_df = check_issues(repo, max_files=max_pr_files)
        main_df = pd.concat([main_df, issues_df], ignore_index=True)

    main_df = main_df[main_df['PR Files Content'].apply(lambda x: bool(x))]

    pd.set_option('display.max_columns', None)  # Show all columns
    pd.set_option('display.max_rows', None)  # Show all rows
    pd.set_option('display.max_colwidth', None)

    file_path = 'issues_list.csv'

    try:
        # Step 1: Load the existing data
        existing_df = pd.read_csv(file_path)
    except FileNotFoundError:
        # If the file does not exist, create an empty DataFrame
        existing_df = pd.DataFrame()

    # Step 2: Concatenate the existing data with the new data
    # Ensure both DataFrames have the same columns for proper concatenation
    if not existing_df.empty and not existing_df.columns.equals(main_df.columns):
        raise ValueError("Columns of existing DataFrame and main DataFrame do not match.")
    combined_df = pd.concat([existing_df, main_df], ignore_index=True)

    # Step 3: Write the combined DataFrame back to the CSV file
    combined_df.to_csv(file_path, index=False)

if __name__ == "__main__":
    main(n=20)