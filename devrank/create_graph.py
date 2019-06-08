import os
import queue
import random
import threading
import time
import dill as pickle

from dotenv import load_dotenv
from neo4j import GraphDatabase
from neobolt.exceptions import ConstraintError
from sgqlc.endpoint.http import HTTPEndpoint
from datetime import datetime
from collections import deque
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


def init_queues(tx):
    result = tx.run("MATCH(u:User) RETURN u")
    for record in result:
        users_already_done.add(record['u']['login'])


def create_user(tx, login):
    tx.run(f"CREATE (a:User {{login: '{login}'}})")


def create_repo(tx, name):
    tx.run(f"CREATE (a:Repo {{name: '{name}'}})")


def create_lang(tx, name):
    tx.run(f"CREATE (a:Language {{name: '{name}'}})")


def create_lang_relation(tx, repo, lang, size):
    tx.run(f"""
            MATCH (lang:Language{{name:'{lang}'}}),(repo:Repo{{name:'{repo}'}}) 
            CREATE UNIQUE (repo)-[r:CONTAINS{{size:{size}}}]->(lang) return r
        """)


def create_relation(tx, repo, user, contributions_count):
    tx.run(f"""
            MATCH (user:User{{login:'{user}'}}),(repo:Repo{{name:'{repo}'}}) 
            CREATE UNIQUE (user)-[r:CONTRIBUTES{{count: {contributions_count}}}]->(repo) return r
        """)


def build_knows_relation(tx):
    print("Building knows relationships")
    tx.run("""
            CALL apoc.periodic.iterate("MATCH (u1:User)-[c1:CONTRIBUTES]->()<-[c2:CONTRIBUTES]-(u2:User) WHERE u1.login < u2.login RETURN *",
            "MERGE (u1)-[r:KNOWS]->(u2) 
            ON CREATE SET r.size = c2.count 
            ON MATCH SET r.size = r.size + c2.count 
            MERGE (u2)-[r2:KNOWS]->(u1) 
            ON CREATE SET r2.size = c1.count 
            ON MATCH SET r2.size = r2.size + c1.count", 
            {batchSize:1000})
            YIELD batches,total
            RETURN batches,total
           """)


def build_codes_relation(tx):
    tx.run("""
            CALL apoc.periodic.iterate(
            "MATCH (u1:User)-[r:CONTRIBUTES]->()-[:CONTAINS]->(l:Language) RETURN *",
            "CALL apoc.merge.relationship(u1, 'CODES_IN', {}, {size: r.size}, l) YIELD rel RETURN rel", 
            {batchSize:10000})
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
    user = result['user']  # TODO here sometimes we have just a string with no user key, if no "user" key, return?
    commit_by_repo = list(filter(lambda contrib: not contrib['repository']['isPrivate'],
                                 user['contributionsCollection']['commitContributionsByRepository']))
    # TODO here there could be a none type somewhere apparently, catch it and in this case just create the user and return?
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


driver.session().read_transaction(init_queues)
start = time.time()
query_for_user("Matoran", 1)
while not users_to_process.empty():
    (u, hops) = users_to_process.get()
    query_for_user(u, hops)
import math
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
print(f"Took {end - start} seconds")
# TODO this is too fast so we get 403...this could work if we do our "safequery" in which we retry after a bit of time until it works (random in 0-2 seconds)
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
