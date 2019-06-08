import os
import time

from dotenv import load_dotenv
from neo4j import GraphDatabase
load_dotenv()

driver = GraphDatabase.driver("bolt://localhost:7687", auth=(os.getenv("DB_USER"), os.getenv("DB_PASS")))


def count_knows_relation(tx):
    print("Counting knows relationships")
    a= tx.run("""
            MATCH (:User)-[k:KNOWS]->() RETURN COUNT(k) as count
           """)
    for aa in a:
        print(aa)
    print(a)


start = time.time()
driver.session().read_transaction(count_knows_relation)
print("...Done")
end = time.time()
print(f"Took {end - start} seconds")
driver.close()
