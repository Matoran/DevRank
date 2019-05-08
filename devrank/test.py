import os
import queue

from dotenv import load_dotenv
from neo4j import GraphDatabase
from sgqlc.endpoint.http import HTTPEndpoint

load_dotenv()

users_already_done = set()
users_to_process = queue.Queue()
repos_already_done = set()
repos_to_process = queue.Queue()

# Used CREATE CONSTRAINT ON (n:User) ASSERT n.login IS UNIQUE / CREATE CONSTRAINT ON (n:Repo) ASSERT n.name IS UNIQUE => to get unique nodes
# CREATE CONSTRAINT ON (n:Language) ASSERT n.name IS UNIQUE

driver = GraphDatabase.driver("bolt://localhost:7687", auth=(os.getenv("DB_USER"), os.getenv("DB_PASS")))

url = 'https://api.github.com/graphql'
TOKEN = os.getenv("GH_KEY")
headers = {'Authorization': f'bearer {TOKEN}'}


def create_user(tx, login):
    tx.run(f"CREATE (a:User {{login: '{login}'}})")


def create_repo(tx, name):
    tx.run(f"CREATE (a:Repo {{name: '{name}'}})")


def create_lang(tx, name):
    tx.run(f"CREATE (a:Language {{name: '{name}'}})")


def create_lang_relation(tx, repo, lang, size):
    tx.run(f"MATCH (lang:Language{{name:'{lang}'}}),(repo:Repo{{name:'{repo}'}}) CREATE UNIQUE (repo)-[r:CONTAINS{{size:{size}}}]->(lang) return r")


def create_relation(tx, repo, user, contributionsCount):
    tx.run(
        f"MATCH (user:User{{login:'{user}'}}),(repo:Repo{{name:'{repo}'}}) CREATE UNIQUE (user)-[r:CONTRIBUTES{{count: {contributionsCount}}}]->(repo) return r")


def build_knows_relation(tx):
    print("Building knows relationships")
    tx.run("MATCH (u1:User)-[:CONTRIBUTES]->()<-[:CONTRIBUTES]-(u2:User) CREATE UNIQUE (u1)-[:KNOWS]->(u2)")


def build_codes_relation(tx):
    tx.run("MATCH (u1:User)-[:CONTRIBUTES]->()-[:CONTAINS]->(l:Language) CREATE UNIQUE (u1)-[:CODES_IN]->(l)")


def compute_pagerank(tx):
    print("calculating pagerank")
    tx.run("CALL algo.pageRank('User','KNOWS',{iterations:20, dampingFactor:0.85, write: true,writeProperty:'pagerank'})")


def users_from_repo(owner, name, after=None):
    if after is not None:
        after = f"\"{after}\""
    else:
        after = "null"
    query = f"""
    query {{
      repository(name: "{name}", owner: "{owner}") {{
        mentionableUsers(first: 100, after: {after}) {{
          totalCount
          pageInfo {{
            hasNextPage
            endCursor
            hasPreviousPage
            startCursor
          }}
          nodes {{
            ... on User {{
              login
            }}
          }}
        }}
      }}
    }}
    """
    endpoint = HTTPEndpoint(url, headers)
    try:
        repo_users = endpoint(query)['data']['repository']['mentionableUsers']
    except Exception as e:
        print(query)
        print(e)
        print(type(e))
        return

    hasNext = repo_users['pageInfo']['hasNextPage']
    next = repo_users['pageInfo']['endCursor']
    users = list(map(lambda node: node['login'], repo_users['nodes']))

    return hasNext, next, users


def process_repo(repo_name, max_hops):
    if max_hops < 0:
        return
    [owner, name] = str.split(repo_name, '/')

    if repo_name in repos_already_done:
        return
    else:
        print(f"add repo:{repo_name} to already done - Hops {max_hops}")
        repos_already_done.add(repo_name)

    users = []

    hasNext = True
    next = None

    while hasNext:
        (hasNext, next, users_retrieved) = users_from_repo(owner, name, next)
        users.extend(users_retrieved)
    # TODO get languages and link
    for u in users:
        if u not in users_already_done:
            users_to_process.put((u, max_hops))


def query_for_user(login, max_hops=3):
    if "[" in login:
        print(f"Skipping {login} because []")
        return
    if max_hops < 0:
        return
    if login in users_already_done:
        print(f"login already done {login}")
        return
    else:
        print(f"add {login} to already done - Hops {max_hops}")
        users_already_done.add(login)
    query = f"""
    query{{
      user(login: "{login}") {{
        contributionsCollection {{
          commitContributionsByRepository(maxRepositories: 100) {{
            repository {{
              nameWithOwner
              isPrivate
            }}          
            contributions(first: 100) {{
              totalCount
            }}
          }}
        }}
      }}
    }}
    """
    endpoint = HTTPEndpoint(url, headers)
    try:
        user = endpoint(query)['data']['user']
    except Exception as e:
        print(e)
        print(type(e))
        return

    commit_by_repo = list(filter(lambda contrib: not contrib['repository']['isPrivate'], user['contributionsCollection']['commitContributionsByRepository']))
    try:
        driver.session().write_transaction(create_user, login)
    except:
        pass
    for contribRepo in commit_by_repo:
        repo_name = contribRepo['repository']['nameWithOwner']
        contribs = contribRepo['contributions']['totalCount']
        if max_hops > 0:
            try:
                driver.session().write_transaction(create_repo, repo_name)
            except:
                pass
        try:
            driver.session().write_transaction(create_relation, repo_name, login, contribs)
        except:
            pass
        if repo_name not in repos_already_done:
            repos_to_process.put(repo_name)

    while not repos_to_process.empty():
        process_repo(repos_to_process.get(), max_hops - 1)


query_for_user("Matoran", 2)
while not users_to_process.empty():
    (u, hops) = users_to_process.get()
    query_for_user(u, hops)

# TODO if a user has hops 0, don't insert in users_to_process but in orphans_to_process and do queries in parallel
# query_for_user("Dawen18", 1)
# query_for_user("Angorance")
# query_for_user("stevenliatti")
# query_for_user("Xcaliburne")
# query_for_user("lekikou")
# query_for_user("ProtectedVariable")
# query_for_user("RaedAbr")
# query_for_user("RalfJung")
# query_for_user("selinux")
# query_for_user("ry")
# query_for_user("torvalds")
# query_for_user("matoran")
# query_for_user("anirul")

# driver.session().write_transaction(build_knows_relation)
# driver.session().write_transaction(build_codes_relation)
# driver.session().write_transaction(compute_pagerank)

driver.close()
