let viz;
const neoURL = "bolt://localhost:7687"
const neoUser = "neo4j"
const neoPass = "supergraph"
const initQuery = 'MATCH p=(:User)-[:CONTRIBUTES]->(:Repo) RETURN p LIMIT 300'

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
                size: "centrality",
                community: "partition"
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
    const config = getConfig(initQuery)
    viz = new NeoVis.default(config);
    viz.registerOnEvent('completed', renderComplete)
    viz.render();
    selectedQuery(initQuery, false)
}

function runNewQuery(query) {
    viz.renderWithCypher(query)
}

function selectedQuery(query, run = true) {
    const searchBar = document.querySelector('#search')
    searchBar.value = query;
    searchBar.focus();
    if (run)
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

function initialQuery() {
    selectedQuery(initQuery);
}

function shortestPath() {
    const user1 = document.querySelector('#user1_path').value
    const user2 = document.querySelector('#user2_path').value

    console.log(user1, user2)
    const query = `MATCH (u1:User { login: '${user1}' }),(u2:User { login: '${user2}' }), p = shortestPath((u1)-[r:KNOWS *]-(u2)) RETURN p`
    selectedQuery(query);
}

function userRelations() {
    const user = document.querySelector('#user').value
    const query = `MATCH (u1:User { login: '${user}' })-[k:KNOWS]->(u2) RETURN *`
    selectedQuery(query);
}

function userContributions(withContributors) {
    const user = document.querySelector('#user').value

    const query = withContributors ? `MATCH p=(:User{login:'${user}'})-[:CONTRIBUTES]->(r:Repo) MATCH p2=(u2:User)-[]->(r) return p,p2` : `MATCH (u1:User { login: '${user}' })-[k:CONTRIBUTES]->(r) RETURN *`
    selectedQuery(query);
}

function userLanguages() {
    const user = document.querySelector('#user').value
    const query = `MATCH (u1:User { login: '${user}' })-[k:CODES_IN]->(l) RETURN *`
    selectedQuery(query);
}

function repoLanguages() {
    const repo = document.querySelector('#repo').value
    const query = `MATCH (u1:Repo { name: '${repo}' })-[k:CONTAINS]->(l) RETURN *`
    selectedQuery(query);
}

function repoContributors() {
    const repo = document.querySelector('#repo').value
    const query = `MATCH (u1:Repo { name: '${repo}' })<-[k:CONTRIBUTES]-(u) RETURN *`
    selectedQuery(query);
}

function languageTopRepos() {
    const language = document.querySelector('#language').value
    const query = `MATCH p=((r:Repo)-[c:CONTAINS]->(n:Language{name:'${language}'})) with r,c,p ORDER BY c.size DESC LIMIT 100 RETURN p`
    selectedQuery(query);
}

function languageTopDevs() {
    const language = document.querySelector('#language').value
    const query = `MATCH p=((u:User)-[c:CODES_IN]->(n:Language{name:'${language}'})) WITH u,c,p ORDER BY c.size DESC LIMIT 100 RETURN p`
    selectedQuery(query);
}

function setupAutocomplete() {

    $('.basicAutoSelect').autoComplete({
        resolver: 'custom',
        events: {
            search: function (qry, callback) {
                session
                    .run(`MATCH (u:User) WHERE LOWER(u.login) STARTS WITH LOWER("${qry}") RETURN u.login`)
                    .then(res => {
                        const records = Array.from(res.records);
                        const names = records.map(r => r._fields[0]).sort((a, b) => a.toLowerCase().localeCompare(b.toLowerCase()));
                        console.warn(names)
                        callback(names);

                    });
            }
        }
    });


    $('.basicAutoSelectRepos').autoComplete({
        resolver: 'custom',
        events: {
            search: function (qry, callback) {
                session
                    .run(`MATCH (u:Repo) WHERE LOWER(u.name) CONTAINS LOWER("${qry}") RETURN u.name`)
                    .then(res => {
                        const records = Array.from(res.records);
                        const names = records.map(r => r._fields[0]).sort((a, b) => a.toLowerCase().localeCompare(b.toLowerCase()));
                        console.warn(names)
                        callback(names);

                    });
            }
        }
    });

    $('.basicAutoSelectLanguages').autoComplete({
        resolver: 'custom',
        events: {
            search: function (qry, callback) {
                session
                    .run(`MATCH (u:Language) WHERE LOWER(u.name) STARTS WITH LOWER("${qry}") RETURN u.name`)
                    .then(res => {
                        const records = Array.from(res.records);
                        const names = records.map(r => r._fields[0]).sort((a, b) => a.toLowerCase().localeCompare(b.toLowerCase()));
                        console.warn(names)
                        callback(names);
                    });
            }
        },
        minLength: 1
    });
}

function renderComplete(stats) {
    if (!stats.record_count) {
        console.warn("No records")
        $('#noRecordToast').toast('show')
    } else {
        $('#noRecordToast').toast('hide')
    }
}

draw();

setupSearch();
setupAutocomplete();
