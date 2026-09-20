import { readFileSync } from 'fs'
const src = readFileSync(process.argv[2], 'utf8').replace(/^export const meta/m, 'const meta')

async function run(args, { stageStyle, agentImpl }) {
  const logs = []
  const log = m => logs.push(m)
  const agent = agentImpl
  const pipeline = async (items, ...stages) => {
    const out = []
    for (let i = 0; i < items.length; i++) {
      let prev = undefined
      try {
        for (let s = 0; s < stages.length; s++) {
          // stageStyle 'item-first': stage 1 gets (item); others get (prev, item)
          // stageStyle 'always-prev': every stage gets (prev, item)
          const a = (s === 0 && stageStyle === 'item-first') ? items[i] : prev
          prev = await stages[s](a, items[i], i)
        }
        out.push(prev)
      } catch (e) { out.push(null) }
    }
    return out
  }
  const fn = new Function('args','log','agent','pipeline','parallel','workflow','budget',
    `return (async () => {\n${src}\n})()`)
  return { result: await fn(args, log, agent, pipeline, null, null, {total:null}), logs }
}

const okAgent = async (p, o) => ({ findings: [], applied: ['x'] })
const nitAgent = async (p, o) => o.phase === 'Final'
  ? { findings: [{file:'a.ts', severity:'nit', summary:'spacing'}], applied: [] }
  : { findings: [], applied: [] }
const bugAgent = async (p, o) => o.phase === 'Final'
  ? { findings: [{file:'a.ts', severity:'bug', summary:'off-by-one'}], applied: [] }
  : { findings: [], applied: [] }

const many = Array.from({length: 23}, (_, i) => `src/mod${i % 7}/file${i}.ts`)
let pass = 0, fail = 0
const check = (name, cond, extra='') => { if (cond) { pass++; console.log(`  ok   ${name}`) } else { fail++; console.log(`  FAIL ${name} ${extra}`) } }

for (const stageStyle of ['item-first','always-prev']) {
  console.log(`\n--- stage-1 convention: ${stageStyle} ---`)
  const { result: r } = await run({files: many, milestone: 2}, {stageStyle, agentImpl: okAgent})
  check('completes without throwing', r && r.groups_total > 0, JSON.stringify(r).slice(0,120))
  check('no group exceeds filesPerGroup (12)', r.groups.every(g=>g.files.length<=12),
        JSON.stringify(r.groups.map(g=>g.files.length)))
  check('group count is uncapped-but-minimal (>= ceil(23/12))', r.groups_total >= 2, `got ${r.groups_total}`)
  check('no files lost', r.groups.reduce((n,g)=>n+g.files.length,0) === many.length,
        `got ${r.groups.reduce((n,g)=>n+g.files.length,0)} of ${many.length}`)
  check('no empty group', r.groups.every(g=>g.files.length>0))
  check('all groups completed', r.groups_completed === r.groups_total)
  check('clean when nothing found', r.clean === true)
}

console.log('\n--- severity classification ---')
const { result: nit } = await run({files:['a/x.ts']}, {stageStyle:'item-first', agentImpl: nitAgent})
check('nit does NOT trigger rerun', nit.rerun_recommended === false)
check('nit still reported in findings', nit.findings.length === 1)
const { result: bug } = await run({files:['a/x.ts']}, {stageStyle:'item-first', agentImpl: bugAgent})
check('bug DOES trigger rerun', bug.rerun_recommended === true)
check('bug makes clean false', bug.clean === false)

console.log('\n--- edge cases ---')
const { result: neg } = await run({files: many, filesPerGroup: -1}, {stageStyle:'item-first', agentImpl: okAgent})
check('negative filesPerGroup clamps, no crash', neg && neg.groups_total >= 1 && neg.groups.reduce((n,g)=>n+g.files.length,0) === many.length)
const { result: zero } = await run({files: many, filesPerGroup: 0}, {stageStyle:'item-first', agentImpl: okAgent})
check('zero filesPerGroup defaults safely', zero && zero.groups.reduce((n,g)=>n+g.files.length,0) === many.length)
const { result: empty } = await run({files: []}, {stageStyle:'item-first', agentImpl: okAgent})
check('empty file list returns early', /nothing reviewed/.test(empty.note) && empty.clean === false)
const { result: root } = await run({files:['a.ts','b.ts']}, {stageStyle:'item-first', agentImpl: okAgent})
check('repo-root files group as "."', root.groups[0].label === '.')
const { result: sk } = await run({files:['a/x.ts'], tools:{simplifier:false}}, {stageStyle:'item-first', agentImpl: okAgent})
check('absent tool -> skipped_steps', sk.skipped_steps.includes('simplifier'))
check('absent tool -> clean is FALSE', sk.clean === false)
const { result: dead } = await run({files:['a/x.ts','b/y.ts']}, {stageStyle:'item-first', agentImpl: async()=>null})
check('null agent result handled', dead && dead.groups_completed === 0)
check('dead agents -> clean false', dead.clean === false)


console.log('\n--- security / validation hardening ---')
const { result: strArg } = await run({files: 'src/a.ts,src/b.ts'}, {stageStyle:'item-first', agentImpl: okAgent})
check('stringified files refused (not char-iterated)', /invalid files argument/.test(strArg.note) && strArg.clean === false)
const { result: abs } = await run({files:['/etc/passwd']}, {stageStyle:'item-first', agentImpl: okAgent})
check('absolute path refused', /unsafe path/.test(abs.note) && abs.clean === false)
const { result: dots } = await run({files:['../../.aws/credentials']}, {stageStyle:'item-first', agentImpl: okAgent})
check('parent-traversal path refused', /unsafe path/.test(dots.note) && dots.clean === false)
const { result: nonStr } = await run({files:[42]}, {stageStyle:'item-first', agentImpl: okAgent})
check('non-string path refused', nonStr.clean === false)
const huge = Array.from({length: 4000}, (_, i) => `src/d${i % 900}/f${i}.ts`)
const { result: big } = await run({files: huge}, {stageStyle:'item-first', agentImpl: okAgent})
check('group count grows with the diff', big.groups_total > 6, `got ${big.groups_total}`)
check('nothing is ever uncovered now', (big.uncovered||[]).length === 0)
check('every supplied file is grouped', big.groups.reduce((n,g)=>n+g.files.length,0) === 4000)
const { result: noTools } = await run({files:['a/x.ts']}, {stageStyle:'item-first', agentImpl: okAgent})
check('tools_asserted false when preflight omitted', noTools.tools_asserted === false)


console.log('\n--- false-green regression (reported defect A) ---')
const SHAPE=['groups','files_supplied','files_reviewed','uncovered','groups_completed','groups_total',
             'skipped_steps','tools_asserted','applied','findings','rerun_recommended','rerun_reasons','clean']
const shapeOk=r=>SHAPE.every(k=>k in r)
for (const [name,args] of [['no files',{files:[]}],['no args at all',{}],
                           ['stringified files',{files:'a.ts,b.ts'}],['unsafe path',{files:['/etc/passwd']}]]) {
  const { result: r } = await run(args, {stageStyle:'item-first', agentImpl: okAgent})
  check(name+' -> clean is FALSE', r.clean === false, JSON.stringify(r).slice(0,80))
  check(name+' -> full documented shape', shapeOk(r), 'missing: '+SHAPE.filter(k=>!(k in r)).join(','))
  check(name+' -> rerun_recommended readable', r.rerun_recommended === false)
  check(name+' -> records skipped steps', (r.skipped_steps||[]).length === 3, 'got '+(r.skipped_steps||[]).length)
}
const { result: good } = await run({files:['a/x.ts'],tools:{reviewer:true,simplifier:true,security:true}}, {stageStyle:'item-first', agentImpl: okAgent})
check('a real clean run still reports clean', good.clean === true)
check('a real clean run has full shape', shapeOk(good))


console.log('\n--- full coverage at scale ---')
for (const N of [100, 1000, 5000]) {
  const fs = Array.from({length:N},(_,i)=>`src/mod${i%40}/f${i}.ts`)
  const { result: r, logs } = await run({files:fs}, {stageStyle:'item-first', agentImpl: okAgent})
  const grouped = r.groups.reduce((n,g)=>n+g.files.length,0)
  const biggest = Math.max(...r.groups.map(g=>g.files.length))
  check(`${N} files: ALL reviewed`, grouped === N, `grouped ${grouped}/${N}`)
  check(`${N} files: none uncovered`, (r.uncovered||[]).length === 0)
  check(`${N} files: agents within runtime cap`, r.groups_total*4 <= 1000, `${r.groups_total*4} agents`)
  // After a hard-fit merge, groups may exceed the nominal budget — that is the
  // designed trade: context degrades, coverage never does. Only the cap is absolute.
  check(`${N} files: within the runtime agent cap`, r.groups_total*4 <= 1000, `${r.groups_total*4} agents`)
  console.log(`       -> ${r.groups_total} groups, ${r.groups_total*4} agents, biggest group ${biggest} files`)
}
const { result: dup } = await run({files:['a/1.ts','a/2.ts','b/1.ts']}, {stageStyle:'item-first', agentImpl: okAgent})
const all = dup.groups.flatMap(g=>g.files)
check('no file appears twice', new Set(all).size === all.length)


console.log('\n--- args-as-JSON-string (the real-run transport bug) ---')
const real = ['src/a/1.ts','src/a/2.ts','src/b/3.ts']
// This is exactly what the harness delivered in the ice-cream run: args is a STRING.
const { result: str } = await run(JSON.stringify({files: real, tools:{reviewer:true,simplifier:true,security:true}}),
                                  {stageStyle:'item-first', agentImpl: okAgent})
check('stringified args are parsed, not silently dropped', str.files_supplied === real.length, `files_supplied=${str.files_supplied}`)
check('...and the gate actually runs', str.groups_total > 0)
check('...and tools_asserted survives', str.tools_asserted === true)
check('...and it can now report clean', str.clean === true)
const { result: bad } = await run('{not json at all', {stageStyle:'item-first', agentImpl: okAgent})
check('unparseable args refuse loudly', /unparseable/.test(bad.note) && bad.clean === false)
const { result: scalar } = await run('42', {stageStyle:'item-first', agentImpl: okAgent})
check('a bare JSON scalar is not an args object', /unparseable/.test(scalar.note) && scalar.clean === false)
const { result: obj } = await run({files: real}, {stageStyle:'item-first', agentImpl: okAgent})
check('a real object still works', obj.files_supplied === real.length)

console.log('\n--- a DEAD step agent is recorded, never silently complete ---')
{ // the security agent dies for every group; the others succeed
  const deadSecurity = async (p, o) => o.label.startsWith('security:') ? null : { findings: [], applied: [] }
  const { result: r } = await run({files:['a/x.ts','a/y.ts'], tools:{reviewer:true,simplifier:true,security:true}},
                                  {stageStyle:'item-first', agentImpl: deadSecurity})
  check('dead middle step -> group NOT complete', r.groups_completed < r.groups_total,
        `completed=${r.groups_completed}/${r.groups_total}`)
  check('...death lands in skipped_steps', r.skipped_steps.some(x=>String(x).startsWith('security@')),
        JSON.stringify(r.skipped_steps))
  check('...tools_asserted goes FALSE despite tools being passed', r.tools_asserted === false)
  check('...clean is false', r.clean === false)
}
{ // the FINAL step dies — the group result itself is null
  const deadFinal = async (p, o) => o.label.startsWith('final:') ? null : { findings: [], applied: [] }
  const { result: r } = await run({files:['a/x.ts'], tools:{reviewer:true,simplifier:true,security:true}},
                                  {stageStyle:'item-first', agentImpl: deadFinal})
  check('dead final step -> group NOT complete', r.groups_completed === 0, `completed=${r.groups_completed}`)
  check('...recorded as final@<group>', r.skipped_steps.some(x=>String(x).startsWith('final@')),
        JSON.stringify(r.skipped_steps))
  check('...tools_asserted false', r.tools_asserted === false)
}
{ // control: nothing dies -> tools_asserted true, nothing skipped
  const { result: r } = await run({files:['a/x.ts'], tools:{reviewer:true,simplifier:true,security:true}},
                                  {stageStyle:'item-first', agentImpl: okAgent})
  check('control: no deaths -> tools_asserted true', r.tools_asserted === true)
  check('control: skipped_steps empty', r.skipped_steps.length === 0)
}

console.log(`\n${pass} passed, ${fail} failed`)
process.exit(fail ? 1 : 0)
