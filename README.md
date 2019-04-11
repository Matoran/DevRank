# DevRank
DevRank is a project for a Web Mining class at HES-SO Master. The idea behind DevRank is to analyse the graph of connection between users and repositories on GitHub and apply the PageRank algorithm to define the influence of developers on the platform.

## Retrieving GitHub Information

We are using the [GitHub GraphQL API](https://developer.github.com/v4/) to retrieve GitHub users and repositories information by starting from several seed users and then looking at repositories they contribute to in order to find more users and continue exploring the graph of connections.

## Storage of the information retrieved

The brain behind our platform will be a graph database, [Neo4J](https://neo4j.com/). As we're exploring GitHub data, we are saving nodes (repositories and users) and saving relations (user contributes to a repository) in the database. At the end of the retrieval session, we will compute direct relations between users that share a common repository (user knows user) to link users between them and then compute the pagerank of each user.

## Data visualisation

We will use [Neovis.js](https://github.com/neo4j-contrib/neovis.js/) to query the graph from the database and visualise it on a webpage.

## How to run

To run the project, you will need a Neo4J database server (this can be done through a Docker Image for example) and replace the url of the database in the frontend HTML file and the scrapping Python program. You will also need to enter your DB credentials in the frontend HTML file and create a `.env` file in the Python program folder containing:

```
DB_USER=<neo4jUser>
DB_PASS=<neo4jPassword>
GH_KEY=<API_KEY_GITHUB>
```

You can get a GitHub API key under "Personal access tokens" in GitHub settings.