import math
import os
import queue
import random
import sys
import threading
import time
from datetime import datetime

from dotenv import load_dotenv
from neo4j import GraphDatabase
from neobolt.exceptions import ConstraintError
from sgqlc.endpoint.http import HTTPEndpoint

load_dotenv()

users_already_done = set()
users_to_process = queue.Queue()
repos_already_done = set()
repos_to_process = queue.Queue()
orphans_to_process = []

# Used
# CREATE CONSTRAINT ON (n:User) ASSERT n.login IS UNIQUE
# CREATE CONSTRAINT ON (n:Repo) ASSERT n.name IS UNIQUE
# CREATE CONSTRAINT ON (n:Language) ASSERT n.name IS UNIQUE

driver = GraphDatabase.driver("bolt://localhost:7687", auth=(os.getenv("DB_USER"), os.getenv("DB_PASS")))

MAX_QUERY_RUNS = 20
url = 'https://api.github.com/graphql'
headers = []
for i in range(10):
    TOKEN = os.getenv(f"GH_KEY{i}")
    if TOKEN is None:
        break
    headers.append({'Authorization': f'bearer {TOKEN}'})


def create_user(tx, login):
    tx.run(f"CREATE (a:User {{login: '{login}'}})")


def create_repo(tx, name):
    tx.run(f"CREATE (a:Repo {{name: '{name}'}})")


def create_lang(tx, name):
    tx.run(f"CREATE (a:Language {{name: '{name}'}})")


def create_lang_relation(tx, repo, lang, size):
    tx.run(f"""
            MATCH (lang:Language{{name:'{lang}'}}),(repo:Repo{{name:'{repo}'}})
            MERGE (repo)-[r:CONTAINS]->(lang)
                ON CREATE SET r.size = {size}
                ON MATCH SET r.size = {size}
            return r
        """)


def create_relation(tx, repo, user, contributions_count):
    tx.run(f"""
            MATCH (user:User{{login:'{user}'}}),(repo:Repo{{name:'{repo}'}})
            MERGE (user)-[r:CONTRIBUTES]->(repo)
                ON CREATE SET r.count = {contributions_count}
                ON MATCH SET r.count = {contributions_count}
            return r
        """)


def safe_query(query, index=0):
    runs = 0
    while runs < MAX_QUERY_RUNS:
        try:
            endpoint = HTTPEndpoint(url, headers[index])
            data = endpoint(query)
            if 'errors' in data:
                print(data['errors'][0]['message'])
                if 'Something went wrong while executing your query.' in data['errors'][0]['message']:
                    return None
                if data['errors'][0]['type'] == 'RATE_LIMITED':
                    reset_at = endpoint("""
                    {
                        rateLimit {
                        remaining
                        resetAt
                        limit
                      }
                    }
                    """)['data']['rateLimit']['resetAt']
                    diff = (datetime.strptime(reset_at, "%Y-%m-%dT%H:%M:%SZ") - datetime.utcnow())
                    print(f"sleep until {reset_at}")
                    time.sleep(diff.total_seconds() + 10)
                    return safe_query(query)
                return None
            data = data['data']
            if data is not None:
                return data
        except Exception as e:
            runs = runs + 1
            time.sleep(random.uniform(.100, 2))
    print("Can't do request after 20 tries")
    print(query)
    exit(1)


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
    repo_users = safe_query(query)['repository']['mentionableUsers']

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
    for u in users:
        if u not in users_already_done:
            if max_hops == 0:
                if u not in orphans_to_process:
                    orphans_to_process.append(u)
            else:
                users_to_process.put((u, max_hops))


def query_for_user(login, max_hops=3, index=0):
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
              languages(first: 3, orderBy: {{field: SIZE, direction: DESC}}) {{
                edges {{
                  size
                  node {{
                    name
                    color
                  }}
                }}
              }}
            }}          
            contributions(first: 100) {{
              totalCount
            }}
          }}
        }}
      }}
    }}
    """
    result = safe_query(query, index)
    if result is None:
        return
    user = result['user']
    commit_by_repo = list(filter(lambda contrib: not contrib['repository']['isPrivate'],
                                 user['contributionsCollection']['commitContributionsByRepository']))
    try:
        driver.session().write_transaction(create_user, login)
    except:
        pass
    for contribRepo in commit_by_repo:
        repo = contribRepo['repository']
        contribs = contribRepo['contributions']['totalCount']
        if max_hops > 0:
            try:
                driver.session().write_transaction(create_repo, repo['nameWithOwner'])
                if repo['languages']:
                    languages = repo['languages']
                    for edge in languages['edges']:
                        size = edge['size']
                        lang = edge['node']
                        try:
                            driver.session().write_transaction(create_lang, lang['name'])
                        except ConstraintError:
                            pass
                        driver.session().write_transaction(create_lang_relation, repo['nameWithOwner'], lang['name'],
                                                           size)
            except:
                pass
        try:
            driver.session().write_transaction(create_relation, repo['nameWithOwner'], login, contribs)
        except:
            pass
        if repo['nameWithOwner'] not in repos_already_done:
            repos_to_process.put(repo['nameWithOwner'])

    while not repos_to_process.empty():
        process_repo(repos_to_process.get(), max_hops - 1)


class OrphanQueryThread(threading.Thread):
    def __init__(self, users):
        threading.Thread.__init__(self)
        self.users = users

    def run(self):
        index = 0
        for username in self.users:
            query_for_user(username, 0, index)
            index = (index + 1) % len(headers)


start = time.time()
if len(headers) == 0:
    print("You have to provide at least one GitHub Key")
    exit(1)

if len(sys.argv) < 3:
    print("Usage: create_graph.py <username> <hops>")
    exit(1)

user = sys.argv[1]
hops = int(sys.argv[2])
print(f"Seed is {user} with {hops} hops")
query_for_user(user, hops)
while not users_to_process.empty():
    (u, hops) = users_to_process.get()
    query_for_user(u, hops)

THREAD_COUNT = math.floor(len(headers) * 1.4)

orphans_chunks = [orphans_to_process[i::THREAD_COUNT] for i in
                  range(THREAD_COUNT)]  # This divides the orphans in THREAD_COUNT groups

threads = list(map(lambda users: OrphanQueryThread(users), orphans_chunks))

print(f"Launching threads for orphans, count of orphans: {len(orphans_to_process)}")
for t in threads:
    t.start()
print("Joining them...")
for t in threads:
    t.join()

print("...Done")
end = time.time()
print(f"Took {end - start} seconds for mining")
print("Starting relations...")


def delete_knows_relation(tx):
    tx.run("""
    Call apoc.periodic.iterate("Match (:User)-[r:KNOWS]->() return r", "delete r", {batchSize: 10000})
           """)


def build_knows_relation(tx):
    print("Building knows relationships")
    tx.run("""
            cypher runtime=slotted CALL apoc.periodic.iterate("MATCH (u1:User)-[c1:CONTRIBUTES]->()<-[c2:CONTRIBUTES]-(u2:User)
            WHERE u1.login < u2.login
            RETURN *",
            "MERGE (u1)-[r:KNOWS]->(u2) 
                ON CREATE SET r.size = c2.count 
                ON MATCH SET r.size = r.size + c2.count
            MERGE (u2)-[r2:KNOWS]->(u1) 
                ON CREATE SET r2.size = c1.count 
                ON MATCH SET r2.size = r2.size + c1.count", 
            {batchSize:100, iterateList:true})
            YIELD batches,total RETURN batches,total
           """)


def delete_codes_relation(tx):
    tx.run("""
    Call apoc.periodic.iterate("Match (:User)-[r:CODES_IN]->() return r", "delete r", {batchSize: 10000})
           """)


def build_codes_relation(tx):
    tx.run("""
            CALL apoc.periodic.iterate(
            "MATCH (u1:User)-[c:CONTRIBUTES]->()-[:CONTAINS]->(l:Language) RETURN *",
            "MERGE (u1)-[r:CODES_IN]->(l) 
                ON CREATE SET r.size = c.count 
                ON MATCH SET r.size = r.size + c.count", 
            {batchSize:10000})
            YIELD batches, total RETURN batches, total
           """)


def compute_pagerank(tx):
    print("calculating pagerank")
    tx.run("""
            CALL algo.pageRank('User','KNOWS',
            {
               iterations:20, 
               dampingFactor:0.85, 
               write: true,
               writeProperty:'pagerank', 
               weightProperty: 'size'
             })
           """)


start = time.time()
driver.session().write_transaction(delete_knows_relation)
driver.session().write_transaction(delete_codes_relation)
driver.session().write_transaction(build_knows_relation)
driver.session().write_transaction(build_codes_relation)
driver.session().write_transaction(compute_pagerank)
print("...Done")
end = time.time()
print(f"Took {end - start} seconds for relations")

driver.close()
