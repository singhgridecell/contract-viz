d3.json('data/graph-data.json')
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
                .strength(-3000)
                .distanceMax(500))
            .force('center', d3.forceCenter(width / 2, height / 2))
            .force('link', d3.forceLink(data.links)
                .id(d => d.id)
                .distance(200)
                .strength(0.5))
            .force('collision', d3.forceCollide().radius(100).strength(0.8))
            .force('x', d3.forceX(width / 2).strength(0.05))
            .force('y', d3.forceY(height / 2).strength(0.05))
            .alphaDecay(0.005)
            .velocityDecay(0.4);

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

        // Create nodes
        const node = g.append('g')
            .selectAll('.node')
            .data(data.nodes)
            .join('g')
            .attr('class', 'node')
            .call(d3.drag()
                .on('start', dragstarted)
                .on('drag', dragged)
                .on('end', dragended));

        node.append('circle')
            .attr('fill', d => getNodeColor(d));

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
        }

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