from rdflib import Graph
from neo4j import GraphDatabase
import json
from pathlib import Path
from flask import Flask, render_template, jsonify

class RdfToNeo4jConverter:
    def __init__(self, uri="bolt://localhost:7687", user="neo4j", password="your_password"):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def load_ttl_to_neo4j(self, ttl_file: Path):
        """Load TTL file into Neo4j"""
        # Parse TTL file
        g = Graph()
        g.parse(ttl_file, format="turtle")
        
        print(f"\nLoading {ttl_file}")
        print(f"Found {len(g)} triples in TTL file")
        
        # Convert to Neo4j
        with self.driver.session() as session:
            # Clear existing data
            session.run("MATCH (n) DETACH DELETE n")
            
            # Create nodes and relationships
            count = 0
            for s, p, o in g:
                # Create nodes
                session.run("""
                    MERGE (subject:Node {uri: $subject})
                    MERGE (object:Node {uri: $object})
                    WITH subject, object
                    MERGE (subject)-[r:RELATIONSHIP {type: $predicate}]->(object)
                """, subject=str(s), object=str(o), predicate=str(p))
                count += 1
                if count % 100 == 0:
                    print(f"Processed {count} triples")
            
            # Verify data was loaded
            node_count = session.run("MATCH (n) RETURN count(n) as count").single()["count"]
            rel_count = session.run("MATCH ()-[r]->() RETURN count(r) as count").single()["count"]
            print(f"\nLoaded {node_count} nodes and {rel_count} relationships into Neo4j")

    def get_graph_data(self):
        """Get graph data in D3.js format"""
        with self.driver.session() as session:
            # Get nodes
            nodes_result = session.run("""
                MATCH (n)
                RETURN DISTINCT n.uri as id, 
                       COALESCE(SPLIT(n.uri, '#')[1], n.uri) as label
            """)
            nodes = [{"id": record["id"], 
                     "label": record["label"]} 
                    for record in nodes_result]

            # Get relationships
            links_result = session.run("""
                MATCH (s)-[r]->(o)
                RETURN s.uri as source, 
                       o.uri as target,
                       r.type as type
            """)
            links = [{"source": record["source"],
                     "target": record["target"],
                     "type": record["type"]}
                    for record in links_result]

            print("\nDebug Information:")
            print(f"Number of nodes: {len(nodes)}")
            print(f"Number of links: {len(links)}")
            print("\nSample nodes:", nodes[:3] if nodes else "No nodes found")
            print("\nSample links:", links[:3] if links else "No links found")
            
            return {"nodes": nodes, "links": links}

    def export_graph_data(self, output_file: str):
        """Export graph data to JSON file"""
        data = self.get_graph_data()
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)

# Flask app for visualization
app = Flask(__name__)

# Store graph data globally
graph_data = None

@app.route('/')
def index():
    return render_template('graph.html')

@app.route('/graph-data')
def get_graph_data():
    return jsonify(graph_data)

def create_html_template():
    """Create D3.js visualization template with improved layout and controls"""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Contract Knowledge Graph</title>
        <script src="https://d3js.org/d3.v7.min.js"></script>
        <style>
            body { margin: 0; padding: 20px; font-family: Arial, sans-serif; }
            #graph { 
                width: 100%; 
                height: 95vh; 
                border: 1px solid #ccc;
                background-color: #f8f9fa;
            }
            .node circle { 
                stroke: #fff; 
                stroke-width: 2px;
                r: 12;
            }
            .node text { 
                font-size: 14px;
                font-weight: bold;
                text-shadow: 0 1px 0 #fff, 1px 0 0 #fff, 0 -1px 0 #fff, -1px 0 0 #fff;
                dx: 15;
            }
            .link { 
                stroke: #999; 
                stroke-opacity: 0.6; 
                stroke-width: 1.5px;
            }
            .link-label {
                font-size: 12px;
                fill: #666;
                text-anchor: middle;
                paint-order: stroke;
                stroke: #ffffff;
                stroke-width: 3px;
                stroke-linejoin: round;
                font-weight: bold;
            }
        </style>
    </head>
    <body>
        <div>
            <button id="zoomIn">Zoom In</button>
            <button id="zoomOut">Zoom Out</button>
            <button id="resetZoom">Reset Zoom</button>
            <button id="centerGraph">Center Graph</button>
        </div>
        <svg id="graph"></svg>
        <script>
            fetch('/graph-data')
                .then(response => response.json())
                .then(data => {
                    const svg = d3.select('#graph');
                    const width = svg.node().parentElement.clientWidth;
                    const height = svg.node().parentElement.clientHeight;

                    // Color scale for different node types
                    const colorScale = d3.scaleOrdinal()
                        .domain(['Contract', 'Party', 'Obligation', 'PaymentTerm', 'Rebate', 'Discount', 'ServiceLevel', 'Penalty'])
                        .range(['#4e79a7', '#f28e2c', '#e15759', '#76b7b2', '#59a14f', '#edc949', '#af7aa1', '#ff9da7']);

                    const zoom = d3.zoom()
                        .scaleExtent([0.1, 4])
                        .on('zoom', zoomed);

                    svg.call(zoom);
                    const g = svg.append('g');
                    
                    // Enhanced force simulation
                    const simulation = d3.forceSimulation(data.nodes)
                        .force('charge', d3.forceManyBody()
                            .strength(-3000)  // Stronger repulsion
                            .distanceMax(500))  // Limit repulsion range
                        .force('center', d3.forceCenter(width / 2, height / 2))
                        .force('link', d3.forceLink(data.links)
                            .id(d => d.id)
                            .distance(200)
                            .strength(0.5))  // Reduced link strength for more flexibility
                        .force('collision', d3.forceCollide().radius(100).strength(0.8))
                        .force('x', d3.forceX(width / 2).strength(0.05))
                        .force('y', d3.forceY(height / 2).strength(0.05))
                        .alphaDecay(0.005)  // Slower cooling
                        .velocityDecay(0.4);  // More damping

                    // Create links
                    const link = g.append('g')
                        .selectAll('line')
                        .data(data.links)
                        .join('line')
                        .attr('class', 'link');

                    // Create link labels
                    const linkLabel = g.append('g')
                        .selectAll('text')
                        .data(data.links)
                        .join('text')
                        .attr('class', 'link-label')
                        .text(d => d.type.split('#').pop());

                    // Create nodes with enhanced dragging
                    const node = g.append('g')
                        .selectAll('.node')
                        .data(data.nodes)
                        .join('g')
                        .attr('class', 'node')
                        .call(d3.drag()
                            .on('start', dragstarted)
                            .on('drag', dragged)
                            .on('end', dragended));

                    // Add circles to nodes with color based on type
                    node.append('circle')
                        .attr('r', 12)
                        .attr('fill', d => getNodeColor(d));

                    // Add labels to nodes
                    node.append('text')
                        .text(d => d.label)
                        .attr('dx', 15)
                        .attr('dy', 5);

                    simulation.on('tick', () => {
                        link
                            .attr('x1', d => d.source.x)
                            .attr('y1', d => d.source.y)
                            .attr('x2', d => d.target.x)
                            .attr('y2', d => d.target.y);

                        linkLabel
                            .attr('x', d => (d.source.x + d.target.x) / 2)
                            .attr('y', d => (d.source.y + d.target.y) / 2);

                        node
                            .attr('transform', d => `translate(${d.x},${d.y})`);
                    });

                    function zoomed(event) {
                        g.attr('transform', event.transform);
                    }

                    // Enhanced drag functions for better positioning
                    function dragstarted(event, d) {
                        if (!event.active) simulation.alphaTarget(0.3).restart();
                        d.fx = d.x;
                        d.fy = d.y;
                    }

                    function dragged(event, d) {
                        d.fx = event.x;
                        d.fy = event.y;
                    }

                    function dragended(event, d) {
                        if (!event.active) simulation.alphaTarget(0);
                        // Keep the node fixed where it was dragged
                        // Comment these out to make nodes stay where dragged
                        // d.fx = null;
                        // d.fy = null;
                    }

                    // Node color function based on node type
                    function getNodeColor(d) {
                        const label = d.label.toLowerCase();
                        if (label.includes('contract')) return colorScale('Contract');
                        if (label.includes('party')) return colorScale('Party');
                        if (label.includes('obligation')) return colorScale('Obligation');
                        if (label.includes('paymentterm')) return colorScale('PaymentTerm');
                        if (label.includes('rebate')) return colorScale('Rebate');
                        if (label.includes('discount')) return colorScale('Discount');
                        if (label.includes('servicelevel')) return colorScale('ServiceLevel');
                        if (label.includes('penalty')) return colorScale('Penalty');
                        return '#ccc';
                    }

                    // Button handlers
                    d3.select('#zoomIn').on('click', () => {
                        svg.transition().call(zoom.scaleBy, 1.5);
                    });

                    d3.select('#zoomOut').on('click', () => {
                        svg.transition().call(zoom.scaleBy, 0.67);
                    });

                    d3.select('#resetZoom').on('click', () => {
                        svg.transition().call(zoom.transform, d3.zoomIdentity);
                    });

                    d3.select('#centerGraph').on('click', () => {
                        const bounds = g.node().getBBox();
                        const dx = bounds.width;
                        const dy = bounds.height;
                        const x = bounds.x + dx/2;
                        const y = bounds.y + dy/2;
                        const scale = 0.6 / Math.max(dx / width, dy / height);
                        const translate = [width/2 - scale * x, height/2 - scale * y];

                        svg.transition().duration(750).call(
                            zoom.transform,
                            d3.zoomIdentity.translate(translate[0], translate[1]).scale(scale)
                        );
                    });

                    // Initial centering
                    setTimeout(() => {
                        d3.select('#centerGraph').dispatch('click');
                    }, 100);
                });
        </script>
    </body>
    </html>
    """
    
    template_dir = Path("templates")
    template_dir.mkdir(exist_ok=True)
    
    with open(template_dir / "graph.html", "w") as f:
        f.write(html)

def main():
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='Convert TTL to Neo4j and visualize')
    parser.add_argument('--ttl', required=True, help='Path to TTL file')
    parser.add_argument('--neo4j-uri', default="bolt://localhost:7687", help='Neo4j URI')
    parser.add_argument('--neo4j-user', default="neo4j", help='Neo4j username')
    parser.add_argument('--neo4j-password', required=True, help='Neo4j password')
    parser.add_argument('--port', type=int, default=5000, help='Flask port')
    
    args = parser.parse_args()

    # Convert and load data
    converter = RdfToNeo4jConverter(
        uri=args.neo4j_uri,
        user=args.neo4j_user,
        password=args.neo4j_password
    )
    
    try:
        # Load TTL into Neo4j
        converter.load_ttl_to_neo4j(Path(args.ttl))
        
        # Get graph data for visualization
        global graph_data
        graph_data = converter.get_graph_data()
        
        # Create visualization template
        create_html_template()
        
        # Start Flask server
        print(f"Starting visualization server on port {args.port}")
        app.run(port=args.port)
        
    finally:
        converter.close()

if __name__ == "__main__":
    main()