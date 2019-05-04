# DevRank

DevRank is a project for a Web Mining class at HES-SO Master. The idea behind DevRank is to analyse the graph of connection between users and repositories on GitHub and apply the PageRank algorithm to define the influence of developers on the platform.

## Context and project objectives

The goal of the project is to create a visual search engine for GitHub. The idea is to be able to visualise the graph of GitHub connections between users, repositories and programming languages. Then, we shall run a pagerank algorithm in order to find the most influent developers in given sets of programing languages. We will also try to detect clusters and closed communities as well as compute shortest paths between users.

## Data

We are using the [GitHub GraphQL API](https://developer.github.com/v4/) to retrieve GitHub users and repositories information by starting from several seed users and then looking at repositories they contribute to in order to find more users and continue exploring the graph of connections. For repositories, the top 3 languages from each repository are retrieverd.

### Storage of the information retrieved

The brain behind our platform will be a graph database, [Neo4J](https://neo4j.com/). As we're exploring GitHub data, we are saving nodes (repositories, users and languages) and saving relations (user contributes to a repository, repository contains language) in the database. At the end of the retrieval session, we will compute direct relations between users that share a common repository (user knows user) to link users between them and then compute the pagerank of each user. We will also compute relations between users and languages if a user contributes to a repository containing the language. The goal is also to include weights on contributions and language relations related to the amount of contributions made by a user.

## Project planning

As of May 3rd 2019, we have built a first version of our retrieval program taking into account users, repositories and languages, with repositories' contributors taken using the `mentionableUsers` present in the repository object. We now have to improve this program to consider direct contributors to the repository as well as the importance of each contribution.  We also need to build the visualisation and querying frontend for our program.

The next steps on the project are the following with suggested deadlines:

- May 10th 2019:
  - New version of the retrieval program with all contributions and their importance
  - Completed planning
- May 17th 2019:
  - Progression on the frontend and visualisations
  - Simple queries
  - Communities detection in the database
- May 24rd 2019:
  - Finish the frontend
  - Data retrieval
  - Clean up
- May 31st 2019: Project submission

## Tools used

### Data visualisation

We will use [Neovis.js](https://github.com/neo4j-contrib/neovis.js/) to query the graph from the database and visualise it on a webpage.

### Python retrieval program

The Python retrieval program is written in Python 3 and uses the following main dependencies:

- [Simple GraphQL Client](https://github.com/profusion/sgqlc) : This GraphQL Clients allows us to interact with the GitHub GraphQL API
- [Neo4J Python Driver](https://neo4j.com/developer/python/): To interact with the Neo4J database
- [DotEnv](https://github.com/theskumar/python-dotenv): To load `.env` files to be accessed as environment variables in code

### Database

We use a [Neo4J](https://neo4j.com/) database with the `Graph Algorithms` and `APOC` plugins installed. The following constraints are applied in the database:

```cypher
CREATE CONSTRAINT ON (n:User) ASSERT n.login IS UNIQUE
CREATE CONSTRAINT ON (n:Repo) ASSERT n.name IS UNIQUE
CREATE CONSTRAINT ON (n:Language) ASSERT n.name IS UNIQUE
```

## How to run

To run the project, you will need a Neo4J database server (this can be done through a Docker Image for example) and replace the url of the database in the frontend HTML file and the data retrieval Python program. You will also need to install the Python dependencies defined in the `requirements.txt` file. To do so, you can use:

```
pip install -r requirements.txt
```

 You will also need to enter your DB credentials in the frontend HTML file and create a `.env` file in the Python program folder containing:

```
DB_USER=<neo4jUser>
DB_PASS=<neo4jPassword>
GH_KEY=<API_KEY_GITHUB>
```

You can get a GitHub API key under "Personal access tokens" in GitHub settings.