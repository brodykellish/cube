import { useEffect, useRef } from 'react'
import * as d3 from 'd3'

interface Node {
  id: string
  type: 'source' | 'effect' | 'mixer'
  name: string
  x?: number
  y?: number
}

interface Edge {
  source: string
  target: string
}

export default function DAGEditor() {
  const svgRef = useRef<SVGSVGElement>(null)

  useEffect(() => {
    if (!svgRef.current) return

    const svg = d3.select(svgRef.current)
    svg.selectAll('*').remove()

    const width = svgRef.current.clientWidth
    const height = svgRef.current.clientHeight

    // Example nodes and edges
    const nodes: Node[] = [
      { id: 'source1', type: 'source', name: 'Shader Source', x: 100, y: 100 },
      { id: 'effect1', type: 'effect', name: 'Glitch', x: 300, y: 100 },
      { id: 'effect2', type: 'effect', name: 'Bulge', x: 500, y: 100 },
    ]

    const edges: Edge[] = [
      { source: 'source1', target: 'effect1' },
      { source: 'effect1', target: 'effect2' },
    ]

    // Create force simulation
    const simulation = d3.forceSimulation(nodes as any)
      .force('link', d3.forceLink(edges).id((d: any) => d.id).distance(100))
      .force('charge', d3.forceManyBody().strength(-300))
      .force('center', d3.forceCenter(width / 2, height / 2))

    // Create links
    const link = svg.append('g')
      .selectAll('line')
      .data(edges)
      .enter()
      .append('line')
      .attr('stroke', '#666')
      .attr('stroke-width', 2)

    // Create nodes
    const node = svg.append('g')
      .selectAll('g')
      .data(nodes)
      .enter()
      .append('g')
      .call(d3.drag<any, any>()
        .on('start', dragstarted)
        .on('drag', dragged)
        .on('end', dragended))

    // Add rectangles for nodes
    node.append('rect')
      .attr('width', 120)
      .attr('height', 60)
      .attr('rx', 8)
      .attr('fill', (d: any) => {
        if (d.type === 'source') return '#3b82f6'
        if (d.type === 'effect') return '#8b5cf6'
        return '#10b981'
      })
      .attr('stroke', '#fff')
      .attr('stroke-width', 2)

    // Add text labels
    node.append('text')
      .attr('x', 60)
      .attr('y', 35)
      .attr('text-anchor', 'middle')
      .attr('fill', '#fff')
      .attr('font-size', '12px')
      .text((d: any) => d.name)

    // Update positions on simulation tick
    simulation.on('tick', () => {
      link
        .attr('x1', (d: any) => d.source.x)
        .attr('y1', (d: any) => d.source.y)
        .attr('x2', (d: any) => d.target.x)
        .attr('y2', (d: any) => d.target.y)

      node.attr('transform', (d: any) => `translate(${d.x - 60},${d.y - 30})`)
    })

    function dragstarted(event: any, d: any) {
      if (!event.active) simulation.alphaTarget(0.3).restart()
      d.fx = d.x
      d.fy = d.y
    }

    function dragged(event: any, d: any) {
      d.fx = event.x
      d.fy = event.y
    }

    function dragended(event: any, d: any) {
      if (!event.active) simulation.alphaTarget(0)
      d.fx = null
      d.fy = null
    }

    return () => {
      simulation.stop()
    }
  }, [])

  return (
    <div className="h-full p-6">
      <h2 className="text-xl font-semibold mb-4">DAG Editor</h2>
      <div className="bg-gray-800 rounded-lg border border-gray-700 h-full">
        <svg ref={svgRef} className="w-full h-full" />
      </div>
    </div>
  )
}


