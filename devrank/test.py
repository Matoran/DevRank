from sgqlc.endpoint.http import HTTPEndpoint
from dotenv import load_dotenv
import os
import queue

from neo4j import GraphDatabase

from neobolt.exceptions import ConstraintError

load_dotenv()

users_already_done = set()
to_process = queue.Queue()

# Used CREATE CONSTRAINT ON (n:User) ASSERT n.login IS UNIQUE / CREATE CONSTRAINT ON (n:Repo) ASSERT n.name IS UNIQUE => to get unique nodes

driver = GraphDatabase.driver("bolt://localhost:7687", auth=(os.getenv("DB_USER"), os.getenv("DB_PASS")))

url = 'https://api.github.com/graphql'
TOKEN = os.getenv("GH_KEY")
headers = {'Authorization': f'bearer {TOKEN}'}


def create_user(tx, login, location):
    tx.run(f"CREATE (a:User {{login: '{login}',location:'{location}'}})")


def create_repo(tx, name):
    tx.run(f"CREATE (a:Repo {{name: '{name}'}})")


def create_relation(tx, repo, user):
    tx.run(f"MATCH (user:User{{login:'{user}'}}),(repo:Repo{{name:'{repo}'}}) CREATE UNIQUE (user)-[r:CONTRIBUTES]->(repo) return r")


def build_knows_relation(tx):
    print("Building knows relationships")
    tx.run("MATCH (u1:User)-[:CONTRIBUTES]->()<-[:CONTRIBUTES]-(u2:User) CREATE UNIQUE (u1)-[:KNOWS]->(u2)")


def compute_pagerank(tx):
    print("calculating pagerank")
    tx.run("CALL algo.pageRank('User','KNOWS',{iterations:20, dampingFactor:0.85, write: true,writeProperty:'pagerank'})")


# TODO pagination for queries, think about queuing next user so that we can dive from the users we find here
def query_for_user(login):
    if login in users_already_done:
        print(f"login already done {login}")
        return
    else:
        print(f"add {login} to already done")
        users_already_done.add(login)
    query = f"""
    query{{
      user(login: "{login}") {{
        name
        login
        location
        repositoriesContributedTo(includeUserRepositories: true ,first: 100, orderBy: {{field: PUSHED_AT, direction: DESC}}, contributionTypes: [COMMIT, PULL_REQUEST], privacy:PUBLIC) {{
          nodes {{
            name
            nameWithOwner
            mentionableUsers(first: 100) {{
              nodes {{
                ... on User {{
                  login
                  name
                  location
                }}
              }}
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
        exit(1)

    repos = user['repositoriesContributedTo']['nodes']
    print(user['name'])
    try:
        driver.session().write_transaction(create_user, user['login'], user['location'])
    except ConstraintError:
        print("User already exists")
    except:
        print("Problem creating user")

    print("=======")
    for repo in repos:
        print(repo['nameWithOwner'])
        print(repo)
        try:
            driver.session().write_transaction(create_repo, repo['nameWithOwner'])
        except ConstraintError:
            print("Repo already exists")
        except:
            print("Problem creating repo")
        driver.session().write_transaction(create_relation, repo['nameWithOwner'], user['login'])
        if repo['mentionableUsers']:
            for collab in repo['mentionableUsers']['nodes']:
                print(collab)
                if collab['login'] not in users_already_done:
                    to_process.put(collab['login'])
                try:
                    driver.session().write_transaction(create_user, collab['login'], collab['location'])
                except ConstraintError:
                    print("User already exists")
                except:
                    print("Problem creating user")
                driver.session().write_transaction(create_relation, repo['nameWithOwner'], collab['login'])
    while not to_process.empty():
        query_for_user(to_process.get())


query_for_user("maximelovino")
query_for_user("Angorance")
query_for_user("stevenliatti")
query_for_user("Xcaliburne")
query_for_user("lekikou")
query_for_user("ProtectedVariable")
query_for_user("RaedAbr")
query_for_user("leadrien")
query_for_user("selinux")
query_for_user("ry")
query_for_user("torvalds")
query_for_user("matoran")
query_for_user("anirul")

driver.session().write_transaction(build_knows_relation)
driver.session().write_transaction(compute_pagerank)

driver.close()