let viz;
function getConfig(query) {
	var config = {
		interaction: {
			hover: true,
			keyboard: {
				enabled: true,
				bindToWindow: false
			},
			navigationButtons: true,
			tooltipDelay: 1000000,
			hideEdgesOnDrag: true,
			zoomView: false
		},
		container_id: "viz",
		server_url: "bolt://localhost:7687",
		server_user: "neo4j",
		server_password: "supergraph",
		labels: {
			"User": {
				caption: "login",
				size: "pagerank"
			},
			"Repo": {
				caption: "name"
			},
			"Language": {
				caption: "name"
			},
		},
		relationships: {
			"CONTRIBUTES": {
				caption: false,
				thickness: "count"
			},
			"KNOWS": {
				caption: false,
				thickness: "size"
			},
			"CONTAINS": {
				caption: false,
				thickness: "size"
			},
			"CODES_IN": {
				caption: false,
				thickness: "size"
			}
		},
		initial_cypher: query
	}
	return config
}


function draw() {
	const config = getConfig('MATCH p=(:User{login:"maximelovino"})-[:CONTRIBUTES]->(:Repo) RETURN p')
	viz = new NeoVis.default(config);
	viz.render();
}

function runNewQuery(query) {
	viz.renderWithCypher(query)
}


function generateQueries() {
	//TODO add parameters field to help build dynamic form to replace them in query
	const queries = [
		{
			name: "User knows",
			query: "MATCH p=(:User{login:'maximelovino'})-[:KNOWS]->() RETURN p"
		},
		{
			name: "User codes in",
			query: "MATCH p=(:User{login:'maximelovino'})-[:CODES_IN]->() RETURN p"
		},
		{
			name: "User contributes",
			query: "MATCH p=(:User{login:'maximelovino'})-[:CONTRIBUTES]->() RETURN p"
		},
		{
			name: "Shortest path between users",
			query: "MATCH (u1:User { login: 'maximelovino' }),(u2:User { login: 'kroitor' }), p = shortestPath((u1)-[r:KNOWS *]-(u2)) RETURN p"
		},
		{
			name: "Repository and languages",
			query: "MATCH p=(:Repo)-[r:CONTAINS]->(:Language) RETURN p"
		},
		{
			name: 'Most prolific users in language',
			query: "MATCH p=((u:User)-[c:CODES_IN]->(n:Language{name:'JavaScript'})) WITH u,c,p ORDER BY c.size DESC LIMIT 10 RETURN p"
		}

	]

	const queriesDiv = document.querySelector('#queries')

	const htmlQueries = queries.map(q => generateUl(q.name, q.query)).join('\n');

	console.log(htmlQueries)

	queriesDiv.innerHTML = htmlQueries

	let allQueries = Array.from(document.querySelectorAll('.query'))

	allQueries.forEach(q => {
		q.onclick = () => {
			selectedQuery(q.dataset['query'])
		}
	})
}

function selectedQuery(query) {
	const searchBar = document.querySelector('#search')
	searchBar.value = query;
	searchBar.focus();
}


function generateUl(name, query) {
	return `
	<ul class="nav flex-column mb-2">
	<li class="nav-item">
		<a class="nav-link query" data-query="${query}">
			${name}
		</a>
	</li>
</ul>
`
}

function setupSearch() {
	const searchBar = document.querySelector('#search')
	searchBar.addEventListener('keydown', (event) => {
		if (event.keyCode == 13) {
			runNewQuery(searchBar.value);
		}
	})
}

draw();
generateQueries();

setupSearch();