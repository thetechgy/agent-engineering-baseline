// Exercise pinned production ACP reporters and renderer, not a replacement parser.
import fs from 'node:fs';
const root=process.env.ACP_SOURCE;
const {CommandReporter}=await import(root+'/src/tool-calls/reporters/CommandReporter.ts');
const {FileChangeReporter}=await import(root+'/src/tool-calls/reporters/FileChangeReporter.ts');
const {AcpToolCallRenderer}=await import(root+'/src/tool-calls/AcpToolCallRenderer.ts');
const {ClientCapabilities}=await import(root+'/src/tool-calls/ClientCapabilities.ts');
const reporter=new CommandReporter(),renderer=new AcpToolCallRenderer(ClientCapabilities.DEFAULT);
const input=JSON.parse(fs.readFileSync(process.argv[2],'utf8')),events=[];
for(const e of input){
 const item=e.params?.item,start=e.method==='item/started';
 if(!item||!['item/started','item/completed'].includes(e.method))continue;
 let facts;
 if(item.type==='commandExecution')facts=start?reporter.started(item):reporter.completed(item,true);
 if(item.type==='fileChange')facts=start?FileChangeReporter.started(item,'none'):FileChangeReporter.completed(item);
 if(facts)events.push({event_type:'session_update',payload:{session_id:e.params.threadId,update:renderer.render(facts)}});
}
const sample=input.find(e=>e.method==='item/completed'&&e.params?.item?.type==='commandExecution').params.item;
const terminalStates={};for(const status of ['failed','declined','interrupted'])terminalStates[status]=renderer.render(reporter.completed({...sample,status},true)).status;
fs.writeFileSync(process.argv[3],JSON.stringify({events,terminalStates},null,2));
console.log(JSON.stringify(terminalStates));
