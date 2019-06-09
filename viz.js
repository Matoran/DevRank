let viz;
const neoURL = "bolt://localhost:7687"
const neoUser = "neo4j"
const neoPass = "supergraph"

const driver = neo4j.v1.driver(
	'bolt://localhost',
	neo4j.v1.auth.basic(neoUser, neoPass)
)
const session = driver.session()

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
		server_url: neoURL,
		server_user: neoUser,
		server_password: neoPass,
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
	const config = getConfig('MATCH p=(:User)-[:CONTRIBUTES]->(:Repo) RETURN p LIMIT 300')
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
			name: "Display graph",
			query: "MATCH p=(:User)-[:CONTRIBUTES]->(:Repo) RETURN p"
		},
		{
			name: "User knows",
			query: "MATCH p=(:User{login:'maximelovino'})-[:KNOWS]->() RETURN p",
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
			name: "User contributes with contributors",
			query: "MATCH p=(:User{login:'maximelovino'})-[:CONTRIBUTES]->()<-[:CONTRIBUTES]-(:User) RETURN p"
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
	runNewQuery(query);
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

function shortestPath() {
	const user1 = document.querySelector('#user1_path').value
	const user2 = document.querySelector('#user2_path').value

	console.log(user1, user2)
	const query = `MATCH (u1:User { login: '${user1}' }),(u2:User { login: '${user2}' }), p = shortestPath((u1)-[r:KNOWS *]-(u2)) RETURN p`
	selectedQuery(query);
}


function setupUserAutocomplete() {
	const selects = document.querySelectorAll('.userSelect')


	selects.forEach(s => {
		const id = s.id
		let select, chosen;

		// Cache the select element as we'll be using it a few times
		select = $(`#${id}`);


		// Init the chosen plugin
		select.chosen();

		// Get the chosen object
		chosen = select.data('chosen');

		$(`#${id}_chosen .chosen-search input`).autocomplete({
			source: function (request, response) {
				console.warn(request)


				session
					.run(`MATCH (u:User) WHERE u.login STARTS WITH "${request.term}" RETURN u.login`)
					.then(res => {
						const autoSelect = $(`#${id}`)
						const records = Array.from(res.records);
						const names = records.map(r => r._fields[0]).sort((a, b) => a.toLowerCase().localeCompare(b.toLowerCase()));
						console.warn(names)
						autoSelect.empty();
						response($.map(names, function (n) {
							autoSelect.append(`<option value="${n}">${n}</option>`);
						}));
						autoSelect.trigger("chosen:updated");
					}).catch(error => {
						console.log(error)
					})
			},
			minLength: 3
		});
	})
}

function setupLanguagesAutocomplete() {
	session
		.run('MATCH (l:Language) return l.name')
		.then(response => {
			const records = Array.from(response.records);
			const names = records.map(r => r._fields[0]).sort((a, b) => a.toLowerCase().localeCompare(b.toLowerCase()))
			console.log(names)
		}).catch(error => {
			console.log(error)
		})
}

function setupReposAutocomplete() {
	session
		.run('MATCH (r:Repo) return r.name')
		.then(response => {
			const records = Array.from(response.records);
			const names = records.map(r => r._fields[0]).sort((a, b) => a.toLowerCase().localeCompare(b.toLowerCase()))
			const repoSelect = document.querySelector('#repo')
			repoSelect.innerHTML = names.map(n => `<option value="${n}">${n}</option>`).join('\n')
		}).catch(error => {
			console.log(error)
		})
}

draw();
generateQueries();

setupSearch();
setupUserAutocomplete();
/*setupLanguagesAutocomplete();
setupReposAutocomplete();*/