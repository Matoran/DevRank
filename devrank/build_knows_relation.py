import os
import time

from dotenv import load_dotenv
from neo4j import GraphDatabase
load_dotenv()

driver = GraphDatabase.driver("bolt://localhost:7687", auth=(os.getenv("DB_USER"), os.getenv("DB_PASS")))


def delete_knows_relation(tx):
    tx.run("""
    Call apoc.periodic.iterate("Match (:User)-[r:KNOWS]->() return r", "delete r", {batchSize: 10000})
           """)


def build_knows_relation(tx):
    print("Building knows relationships")
    tx.run("""
            cypher runtime=slotted CALL apoc.periodic.iterate("MATCH (u1:User)-[c1:CONTRIBUTES]->()<-[c2:CONTRIBUTES]-(u2:User) WHERE u1.login < u2.login RETURN *", "MERGE (u1)-[r:KNOWS]->(u2) ON CREATE SET r.size = c2.count ON MATCH SET r.size = r.size + c2.count MERGE (u2)-[r2:KNOWS]->(u1) ON CREATE SET r2.size = c1.count ON MATCH SET r2.size = r2.size + c1.count",  {batchSize:100, iterateList:true}) YIELD batches,total RETURN batches,total
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


start = time.time()
driver.session().write_transaction(delete_knows_relation)
driver.session().write_transaction(build_knows_relation)
print("...Done")
end = time.time()
print(f"Took {end - start} seconds")
driver.close()
