import type { ElementContent, Root, RootContent, Text } from 'hast'

const citationPattern = /(?:\[(\d+)]|【(\d+)】)/g

function transformRootChildren(children: RootContent[], sourceCount: number): RootContent[] {
  const transformed: RootContent[] = []
  for (const child of children) {
    if (child.type === 'text') transformed.push(...splitCitationText(child, sourceCount))
    else if (child.type === 'element') transformed.push({ ...child, children: transformElementChildren(child.children, sourceCount, child.tagName) })
    else transformed.push(child)
  }
  return transformed
}

function transformElementChildren(children: ElementContent[], sourceCount: number, parentTag?: string): ElementContent[] {
  if (parentTag === 'code' || parentTag === 'pre' || parentTag === 'a') return children
  return children.flatMap((child) => {
    if (child.type === 'text') return splitCitationText(child, sourceCount)
    if (child.type === 'element') return [{ ...child, children: transformElementChildren(child.children, sourceCount, child.tagName) }]
    return [child]
  })
}

function splitCitationText(node: Text, sourceCount: number): ElementContent[] {
  const output: ElementContent[] = []
  let lastIndex = 0
  for (const match of node.value.matchAll(citationPattern)) {
    const number = Number(match[1] ?? match[2])
    if (!Number.isSafeInteger(number) || number < 1 || number > sourceCount || match.index === undefined) continue
    if (match.index > lastIndex) output.push({ type: 'text', value: node.value.slice(lastIndex, match.index) })
    output.push({ type: 'element', tagName: 'sup', properties: { dataCitation: number }, children: [{ type: 'text', value: `[${number}]` }] })
    lastIndex = match.index + match[0].length
  }
  if (lastIndex === 0) return [node]
  if (lastIndex < node.value.length) output.push({ type: 'text', value: node.value.slice(lastIndex) })
  return output
}

export function rehypeCitations(sourceCount: number) {
  return (tree: Root) => { tree.children = transformRootChildren(tree.children, sourceCount) }
}
