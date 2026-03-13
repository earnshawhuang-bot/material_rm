import { useState, useMemo } from "react";

const USERS = [
  { username: "admin", password: "123456", displayName: "管理员", department: "PPIC", role: "admin" },
  { username: "caigou01", password: "123456", displayName: "张明", department: "采购", role: "user" },
];

const AGING = {
  A: { label: "≤30天", color: "#10b981", bg: "#ecfdf5", bd: "#a7f3d0" },
  B: { label: ">30~90天", color: "#3b82f6", bg: "#eff6ff", bd: "#bfdbfe" },
  C: { label: ">90~180天", color: "#f59e0b", bg: "#fffbeb", bd: "#fde68a" },
  D: { label: ">180~360天", color: "#f97316", bg: "#fff7ed", bd: "#fed7aa" },
  E: { label: ">360天", color: "#ef4444", bg: "#fef2f2", bd: "#fecaca" },
};

const RISK = {
  defective: { label: "不良品", color: "#ef4444", bg: "#fef2f2", bd: "#fecaca", icon: "✗" },
  aging_warn: { label: "库龄预警", color: "#f97316", bg: "#fff7ed", bd: "#fed7aa", icon: "⏱" },
  normal: { label: "正常", color: "#10b981", bg: "#ecfdf5", bd: "#a7f3d0", icon: "✓" },
};

const DEPTS = ["采购","质量","研发","生产","PPIC&仓库","PPIC&质量","采购/质量","质量/研发"];
const PLANS = ["冻结","退货","转内贸退货","特采释放","料废外卖","按呆滞料流程处理","绕卷","索赔","试机纸","其他"];
const STATUSES = ["待处理","讨论中","进行中","待定","已完成","已关闭"];

const STATUS_COLORS = {
  "未分配":{c:"#94a3b8",bg:"#f1f5f9"},"待处理":{c:"#94a3b8",bg:"#f1f5f9"},
  "讨论中":{c:"#3b82f6",bg:"#eff6ff"},"进行中":{c:"#f59e0b",bg:"#fffbeb"},
  "待定":{c:"#8b5cf6",bg:"#f5f3ff"},"已完成":{c:"#10b981",bg:"#ecfdf5"},
  "已关闭":{c:"#6b7280",bg:"#f3f4f6"},
};

function getRisk(q, a) {
  if (q === "N") return "defective";
  if (["D","E"].includes(a)) return "aging_warn";
  return "normal";
}

// 生成模拟数据
const MATS = [
  {code:"1101000000",name:"液包纸UB000-SWED75g654mm",cat:"Paper",sup:"利乐拉伐包材(昆山)",u:"M"},
  {code:"1121000002",name:"镀铝膜MFP-PET12μm1466mm",cat:"AL",sup:"上海英冠镀膜科技",u:"M"},
  {code:"1111000001",name:"Sabic HDPE CC860",cat:"PE",sup:"沙特基础工业(中国)",u:"KG"},
  {code:"1101000140",name:"液包纸154g1054mmFSC",cat:"Paper",sup:"斯道拉恩索(广西)",u:"M"},
  {code:"1121300004",name:"高阻隔膜镀氧化铝MDOPE30um",cat:"AL",sup:"汕头市鑫瑞奇诺包装",u:"M"},
  {code:"1111000025",name:"LDPE Dow 5004I",cat:"PE",sup:"陶氏化学(上海)",u:"KG"},
  {code:"1101000200",name:"液包纸SBS280g720mm",cat:"Paper",sup:"宁波亚洲浆纸业",u:"M"},
  {code:"1121200001",name:"K膜MK12-25μm1512mm",cat:"AL",sup:"江阴市隆辉包装材料",u:"M"},
];

const AP = ["A","A","A","A","B","B","B","C","C","D","D","E"];
const QP = ["Y","Y","Y","Y","Y","Y","Y","Y","Y","N"];
const DATA = []; const ACTIONS = {};

for (let i = 0; i < 100; i++) {
  const m = MATS[i%MATS.length], ag = AP[i%AP.length], qf = QP[i%QP.length];
  const bn = `${1900000000+i*37}`, st = Math.round(1000+Math.random()*50000);
  const cost = Math.round(st*(0.5+Math.random()*8)*100)/100;
  const bd = new Date(2025,Math.floor(Math.random()*12),1+Math.floor(Math.random()*28));
  const ed = new Date(bd); ed.setMonth(ed.getMonth()+18);
  const risk = getRisk(qf, ag);
  DATA.push({
    id:i+1,batchNo:bn,materialCode:m.code,materialName:m.name,
    plant:i%2===0?"3000":"3001",storageLocDesc:qf==="N"?"原料不良库":"主材库(一厂)",
    binLocation:`YL-${i%9+1}${String.fromCharCode(65+i%6)}${String(i%20).padStart(2,"0")}`,
    actualStock:st,weightKg:Math.round(st*(m.u==="KG"?1:0.049)*100)/100,
    productionDate:bd.toISOString().split("T")[0],
    inboundDate:bd.toISOString().split("T")[0],
    expiryDate:ed.toISOString().split("T")[0],
    qualityFlag:qf,agingCategory:ag,financialCost:cost,
    supplierName:m.sup,unit:m.u,currency:"CNY",rmCategory:m.cat,
    riskLevel:risk,isFrozen:i%25===0?1:0,
  });
  if (risk !== "normal" && i%4===0) {
    ACTIONS[bn] = {
      dept:DEPTS[i%DEPTS.length],plan:PLANS[i%PLANS.length],
      status:STATUSES[i%STATUSES.length],remark:i%5===0?`C2026010${i%9}0009`:"",
      updatedBy:"张明",updatedAt:"2026-02-28 14:30",
    };
  }
}

// 通用组件
const Tag = ({children,color,bg,bd}) => (
  <span style={{display:"inline-flex",alignItems:"center",gap:4,padding:"2px 10px",borderRadius:6,fontSize:12,fontWeight:600,color,backgroundColor:bg,border:`1px solid ${bd||bg}`,whiteSpace:"nowrap"}}>{children}</span>
);

const RiskTag = ({level}) => { const r=RISK[level]; return r ? <Tag color={r.color} bg={r.bg} bd={r.bd}>{r.icon} {r.label}</Tag> : null; };
const AgingTag = ({cat}) => { const a=AGING[cat]; return a ? <Tag color={a.color} bg={a.bg} bd={a.bd}>{a.label}</Tag> : null; };
const StatusTag = ({s}) => { const c=STATUS_COLORS[s]||STATUS_COLORS["未分配"]; return <Tag color={c.c} bg={c.bg}>{s||"未分配"}</Tag>; };

const Sel = ({label,value,onChange,options,required}) => (
  <div style={{display:"flex",flexDirection:"column",gap:6}}>
    <label style={{fontSize:13,fontWeight:600,color:"#374151"}}>{label}{required&&<span style={{color:"#ef4444"}}> *</span>}</label>
    <select value={value||""} onChange={e=>onChange(e.target.value)} style={{padding:"8px 12px",borderRadius:8,border:"1.5px solid #d1d5db",fontSize:14,color:"#1f2937",outline:"none",cursor:"pointer"}}>
      <option value="">请选择</option>{options.map(o=><option key={o} value={o}>{o}</option>)}
    </select>
  </div>
);

const Inp = ({label,value,onChange,placeholder,multi,type="text",required}) => (
  <div style={{display:"flex",flexDirection:"column",gap:6}}>
    <label style={{fontSize:13,fontWeight:600,color:"#374151"}}>{label}{required&&<span style={{color:"#ef4444"}}> *</span>}</label>
    {multi ? <textarea value={value||""} onChange={e=>onChange(e.target.value)} placeholder={placeholder} rows={3} style={{padding:"8px 12px",borderRadius:8,border:"1.5px solid #d1d5db",fontSize:14,outline:"none",fontFamily:"inherit",width:"100%",boxSizing:"border-box",resize:"vertical"}}/>
      : <input type={type} value={value||""} onChange={e=>onChange(e.target.value)} placeholder={placeholder} style={{padding:"8px 12px",borderRadius:8,border:"1.5px solid #d1d5db",fontSize:14,outline:"none",width:"100%",boxSizing:"border-box"}}/>}
  </div>
);

// 登录页
function Login({onLogin}) {
  const [u,setU]=useState(""); const [p,setP]=useState(""); const [err,setErr]=useState("");
  const go=()=>{const user=USERS.find(x=>x.username===u&&x.password===p);if(user)onLogin(user);else setErr("用户名或密码错误");};
  const is={width:"100%",padding:"12px 16px",borderRadius:10,border:"1.5px solid rgba(255,255,255,0.1)",fontSize:14,color:"#f1f5f9",backgroundColor:"rgba(255,255,255,0.05)",outline:"none",boxSizing:"border-box"};
  return (
    <div style={{minHeight:"100vh",display:"flex",alignItems:"center",justifyContent:"center",background:"linear-gradient(145deg,#0f172a,#1e293b,#0f172a)",fontFamily:"'Noto Sans SC',sans-serif"}}>
      <div style={{width:400,padding:"44px 36px",borderRadius:20,background:"rgba(255,255,255,0.03)",border:"1px solid rgba(255,255,255,0.08)",boxShadow:"0 25px 60px rgba(0,0,0,0.3)"}}>
        <div style={{textAlign:"center",marginBottom:36}}>
          <div style={{width:52,height:52,borderRadius:14,margin:"0 auto 14px",background:"linear-gradient(135deg,#6366f1,#4f46e5)",display:"flex",alignItems:"center",justifyContent:"center",boxShadow:"0 8px 24px rgba(99,102,241,0.3)"}}>
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2"><path d="M22 8.35V20a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V8.35A2 2 0 0 1 3.26 6.5l8-3.2a2 2 0 0 1 1.48 0l8 3.2A2 2 0 0 1 22 8.35Z"/></svg>
          </div>
          <h1 style={{fontSize:20,fontWeight:700,color:"#f1f5f9",margin:0}}>原材料库存分析平台</h1>
          <p style={{fontSize:12,color:"#64748b",marginTop:6}}>RM Inventory Analysis & Action Platform</p>
        </div>
        <div style={{display:"flex",flexDirection:"column",gap:18}}>
          <div><label style={{fontSize:13,fontWeight:500,color:"#94a3b8",display:"block",marginBottom:8}}>用户名</label><input type="text" value={u} onChange={e=>setU(e.target.value)} placeholder="请输入用户名" onKeyDown={e=>e.key==="Enter"&&go()} style={is}/></div>
          <div><label style={{fontSize:13,fontWeight:500,color:"#94a3b8",display:"block",marginBottom:8}}>密码</label><input type="password" value={p} onChange={e=>setP(e.target.value)} placeholder="请输入密码" onKeyDown={e=>e.key==="Enter"&&go()} style={is}/></div>
          {err&&<div style={{padding:"10px 14px",borderRadius:8,fontSize:13,color:"#fca5a5",backgroundColor:"rgba(239,68,68,0.1)"}}>{err}</div>}
          <button onClick={go} style={{padding:"12px",borderRadius:10,border:"none",fontSize:15,fontWeight:600,color:"#fff",cursor:"pointer",background:"linear-gradient(135deg,#6366f1,#4f46e5)",boxShadow:"0 4px 16px rgba(99,102,241,0.3)"}}>登 录</button>
        </div>
        <div style={{marginTop:24,padding:"12px 14px",borderRadius:10,backgroundColor:"rgba(99,102,241,0.06)",fontSize:12,color:"#94a3b8",lineHeight:1.7}}>
          <span style={{fontWeight:600,color:"#a5b4fc"}}>演示账号：</span><br/>管理员: admin / 123456<br/>采购: caigou01 / 123456
        </div>
      </div>
    </div>
  );
}

// 导航
function Nav({user,onLogout,page,onNav}) {
  const items=[{k:"inventory",l:"库存明细"},{k:"pending",l:"待处理"},...(user.role==="admin"?[{k:"upload",l:"数据上传"}]:[])];
  return (
    <div style={{height:54,display:"flex",alignItems:"center",justifyContent:"space-between",padding:"0 24px",backgroundColor:"#fff",borderBottom:"1px solid #e5e7eb",position:"sticky",top:0,zIndex:100}}>
      <div style={{display:"flex",alignItems:"center",gap:28}}>
        <div style={{display:"flex",alignItems:"center",gap:8,cursor:"pointer"}} onClick={()=>onNav("inventory")}>
          <div style={{width:30,height:30,borderRadius:8,background:"linear-gradient(135deg,#6366f1,#4f46e5)",display:"flex",alignItems:"center",justifyContent:"center"}}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.5"><path d="M22 8.35V20a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V8.35A2 2 0 0 1 3.26 6.5l8-3.2a2 2 0 0 1 1.48 0l8 3.2A2 2 0 0 1 22 8.35Z"/></svg>
          </div>
          <span style={{fontSize:14,fontWeight:700,color:"#1f2937"}}>RM Inventory</span>
        </div>
        <nav style={{display:"flex",gap:4}}>
          {items.map(n=><button key={n.k} onClick={()=>onNav(n.k)} style={{padding:"5px 14px",borderRadius:8,border:"none",fontSize:13,fontWeight:page===n.k?600:500,color:page===n.k?"#4f46e5":"#6b7280",backgroundColor:page===n.k?"#eef2ff":"transparent",cursor:"pointer"}}>{n.l}</button>)}
        </nav>
      </div>
      <div style={{display:"flex",alignItems:"center",gap:12}}>
        <span style={{fontSize:13,fontWeight:600,color:"#1f2937"}}>{user.displayName}</span>
        <span style={{fontSize:11,color:"#9ca3af"}}>({user.department})</span>
        <button onClick={onLogout} style={{padding:"4px 10px",borderRadius:6,border:"1px solid #e5e7eb",fontSize:12,color:"#9ca3af",backgroundColor:"#fff",cursor:"pointer"}}>退出</button>
      </div>
    </div>
  );
}

// 列表页
function ListPage({onView}) {
  const [f,setF]=useState({plant:"",cat:"",aging:"",risk:"",kw:""});
  const [pg,setPg]=useState(1);
  const [sortKey,setSortKey]=useState("aging");
  const [sortDir,setSortDir]=useState("desc");
  const ps=15;
  const ao={E:5,D:4,C:3,B:2,A:1};

  const stats=useMemo(()=>{
    const t=DATA.length,d=DATA.filter(r=>r.riskLevel==="defective").length,a=DATA.filter(r=>r.riskLevel==="aging_warn").length;
    const p=DATA.filter(r=>r.riskLevel!=="normal"&&!ACTIONS[r.batchNo]).length;
    const done=Object.values(ACTIONS).filter(x=>x.status==="已完成").length;
    return {total:t,def:d,aw:a,pend:p,done};
  },[]);

  const list=useMemo(()=>{
    let r=[...DATA];
    if(f.plant)r=r.filter(x=>x.plant===f.plant);
    if(f.cat)r=r.filter(x=>x.rmCategory===f.cat);
    if(f.aging)r=r.filter(x=>x.agingCategory===f.aging);
    if(f.risk)r=r.filter(x=>x.riskLevel===f.risk);
    if(f.kw){const k=f.kw.toLowerCase();r=r.filter(x=>x.materialCode.includes(k)||x.materialName.toLowerCase().includes(k)||x.supplierName.toLowerCase().includes(k)||x.batchNo.includes(k));}
    r.sort((a,b)=>{
      if(sortKey==="aging"){return sortDir==="desc"?(ao[b.agingCategory]||0)-(ao[a.agingCategory]||0):(ao[a.agingCategory]||0)-(ao[b.agingCategory]||0);}
      return sortDir==="desc"?b.financialCost-a.financialCost:a.financialCost-b.financialCost;
    });
    return r;
  },[f,sortKey,sortDir]);

  const tp=Math.ceil(list.length/ps);
  const pd=list.slice((pg-1)*ps,pg*ps);
  const uf=(k,v)=>{setF(p=>({...p,[k]:v}));setPg(1);};

  const RBtn=({rk,label,cnt,icon,color,bg,bd})=>{
    const on=f.risk===rk;
    return <button onClick={()=>uf("risk",on?"":rk)} style={{display:"flex",alignItems:"center",gap:5,padding:"6px 12px",borderRadius:8,border:`1.5px solid ${on?bd:"#e5e7eb"}`,backgroundColor:on?bg:"#fff",fontSize:13,fontWeight:on?600:500,color:on?color:"#64748b",cursor:"pointer"}}>
      {icon} {label} <span style={{padding:"1px 6px",borderRadius:10,fontSize:11,fontWeight:700,backgroundColor:on?color+"18":"#f1f5f9",color:on?color:"#94a3b8"}}>{cnt}</span>
    </button>;
  };

  return (
    <div style={{padding:"20px 24px",maxWidth:1480,margin:"0 auto"}}>
      {/* 统计卡片 */}
      <div style={{display:"grid",gridTemplateColumns:"repeat(5,1fr)",gap:12,marginBottom:20}}>
        {[
          {l:"总批次",v:stats.total,i:"Σ",c:"#6366f1",bg:"#eef2ff"},
          {l:"不良品",v:stats.def,i:"✗",c:"#ef4444",bg:"#fef2f2",s:`${(stats.def/stats.total*100).toFixed(1)}%`},
          {l:"库龄预警",v:stats.aw,i:"⏱",c:"#f97316",bg:"#fff7ed",s:`${(stats.aw/stats.total*100).toFixed(1)}%`},
          {l:"待处理",v:stats.pend,i:"◷",c:"#f59e0b",bg:"#fffbeb"},
          {l:"已完成",v:stats.done,i:"✓",c:"#10b981",bg:"#ecfdf5"},
        ].map(c=>(
          <div key={c.l} style={{padding:"14px 18px",borderRadius:12,backgroundColor:"#fff",border:"1px solid #f0f0f0",display:"flex",alignItems:"center",gap:12}}>
            <div style={{width:40,height:40,borderRadius:10,backgroundColor:c.bg,display:"flex",alignItems:"center",justifyContent:"center",fontSize:17,fontWeight:800,color:c.c}}>{c.i}</div>
            <div><div style={{fontSize:11,color:"#9ca3af",fontWeight:500}}>{c.l}</div><div style={{fontSize:20,fontWeight:800,color:"#1f2937"}}>{c.v}{c.s&&<span style={{fontSize:11,color:c.c,marginLeft:5}}>{c.s}</span>}</div></div>
          </div>
        ))}
      </div>

      {/* 筛选 */}
      <div style={{display:"flex",flexDirection:"column",gap:10,padding:"14px 18px",backgroundColor:"#fff",borderRadius:12,border:"1px solid #f0f0f0",marginBottom:14}}>
        <div style={{display:"flex",alignItems:"center",gap:10,flexWrap:"wrap"}}>
          <span style={{fontSize:13,fontWeight:600,color:"#6b7280"}}>筛选</span>
          {[["plant",{"":" 全部工厂","3000":"3000 一厂","3001":"3001 二厂"}],["cat",{"":"全部类别","Paper":"Paper 纸板","AL":"AL 铝箔","PE":"PE 膜"}],["aging",{"":"全部库龄",...Object.fromEntries(Object.entries(AGING).map(([k,v])=>[k,`${k} ${v.label}`]))}]].map(([key,opts])=>(
            <select key={key} value={f[key]} onChange={e=>uf(key,e.target.value)} style={{padding:"6px 10px",borderRadius:8,border:"1.5px solid #e5e7eb",fontSize:13,color:"#374151",cursor:"pointer"}}>
              {Object.entries(opts).map(([v,l])=><option key={v} value={v}>{l}</option>)}
            </select>
          ))}
          <div style={{flex:1,minWidth:180,display:"flex",alignItems:"center",gap:6,padding:"6px 10px",borderRadius:8,border:"1.5px solid #e5e7eb"}}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#9ca3af" strokeWidth="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
            <input value={f.kw} onChange={e=>uf("kw",e.target.value)} placeholder="搜索物料/供应商/批次号..." style={{border:"none",outline:"none",flex:1,fontSize:13,color:"#374151",backgroundColor:"transparent"}}/>
          </div>
        </div>
        <div style={{display:"flex",alignItems:"center",gap:8}}>
          <span style={{fontSize:12,color:"#9ca3af",marginRight:2}}>风险筛选</span>
          <RBtn rk="defective" label="不良品" cnt={stats.def} icon="✗" color="#ef4444" bg="#fef2f2" bd="#fecaca"/>
          <RBtn rk="aging_warn" label="库龄预警" cnt={stats.aw} icon="⏱" color="#f97316" bg="#fff7ed" bd="#fed7aa"/>
          <RBtn rk="normal" label="正常" cnt={stats.total-stats.def-stats.aw} icon="✓" color="#10b981" bg="#ecfdf5" bd="#a7f3d0"/>
          {f.risk&&<button onClick={()=>uf("risk","")} style={{padding:"4px 10px",borderRadius:6,border:"none",fontSize:12,color:"#6366f1",backgroundColor:"#eef2ff",cursor:"pointer",fontWeight:600}}>清除</button>}
        </div>
      </div>

      {/* 排序 */}
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:10}}>
        <span style={{fontSize:13,color:"#9ca3af"}}>共 <b style={{color:"#374151"}}>{list.length}</b> 条</span>
        <div style={{display:"flex",gap:6}}>
          {[["aging","库龄"],["cost","金额"]].map(([k,l])=>(
            <button key={k} onClick={()=>{if(sortKey===k)setSortDir(d=>d==="desc"?"asc":"desc");else{setSortKey(k);setSortDir("desc");}}}
              style={{padding:"3px 8px",borderRadius:6,border:"1px solid #e5e7eb",fontSize:12,cursor:"pointer",color:sortKey===k?"#4f46e5":"#9ca3af",backgroundColor:sortKey===k?"#eef2ff":"#fff",fontWeight:sortKey===k?600:400}}>
              {l} {sortKey===k&&(sortDir==="desc"?"↓":"↑")}
            </button>
          ))}
        </div>
      </div>

      {/* 表格 */}
      <div style={{backgroundColor:"#fff",borderRadius:12,border:"1px solid #f0f0f0",overflow:"hidden"}}>
        <div style={{overflowX:"auto"}}>
          <table style={{width:"100%",borderCollapse:"collapse",fontSize:13}}>
            <thead><tr style={{backgroundColor:"#f8fafc"}}>
              {["物料编号","物料名称","批次编号","工厂","类别","库龄","风险标记","实际库存","成本额(¥)","处理状态","操作"].map(h=>
                <th key={h} style={{padding:"10px 12px",textAlign:"left",fontWeight:600,color:"#64748b",fontSize:12,borderBottom:"1px solid #f0f0f0",whiteSpace:"nowrap"}}>{h}</th>
              )}
            </tr></thead>
            <tbody>{pd.map(row=>{
              const bg=row.riskLevel==="defective"?"#fef2f2":row.riskLevel==="aging_warn"?"#fffcf7":"transparent";
              const st=ACTIONS[row.batchNo]?.status||"未分配";
              return (
                <tr key={row.batchNo} style={{borderBottom:"1px solid #f7f7f7",backgroundColor:bg,cursor:"pointer"}}
                  onClick={()=>onView(row.batchNo)}
                  onMouseEnter={e=>e.currentTarget.style.backgroundColor="#f8fafc"}
                  onMouseLeave={e=>e.currentTarget.style.backgroundColor=bg}>
                  <td style={{padding:"10px 12px",fontFamily:"monospace",fontSize:12,color:"#6366f1",fontWeight:600}}>{row.materialCode}</td>
                  <td style={{padding:"10px 12px",maxWidth:180,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap",color:"#1f2937"}}>{row.materialName}</td>
                  <td style={{padding:"10px 12px",fontFamily:"monospace",fontSize:12,color:"#64748b"}}>{row.batchNo}</td>
                  <td style={{padding:"10px 12px",color:"#64748b"}}>{row.plant}</td>
                  <td style={{padding:"10px 12px"}}><Tag color={row.rmCategory==="Paper"?"#92400e":row.rmCategory==="AL"?"#1d4ed8":"#047857"} bg={row.rmCategory==="Paper"?"#fef3c7":row.rmCategory==="AL"?"#dbeafe":"#d1fae5"}>{row.rmCategory}</Tag></td>
                  <td style={{padding:"10px 12px"}}><AgingTag cat={row.agingCategory}/></td>
                  <td style={{padding:"10px 12px"}}><RiskTag level={row.riskLevel}/></td>
                  <td style={{padding:"10px 12px",fontVariantNumeric:"tabular-nums",fontWeight:500}}>{row.actualStock.toLocaleString()}</td>
                  <td style={{padding:"10px 12px",fontVariantNumeric:"tabular-nums",fontWeight:500}}>¥{row.financialCost.toLocaleString()}</td>
                  <td style={{padding:"10px 12px"}}><StatusTag s={st}/></td>
                  <td style={{padding:"10px 12px"}}><button onClick={e=>{e.stopPropagation();onView(row.batchNo);}} style={{padding:"4px 10px",borderRadius:6,border:"1px solid #e0e7ff",backgroundColor:"#f5f3ff",fontSize:12,fontWeight:600,color:"#4f46e5",cursor:"pointer"}}>处理</button></td>
                </tr>
              );
            })}</tbody>
          </table>
        </div>
        <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",padding:"12px 18px",borderTop:"1px solid #f0f0f0"}}>
          <span style={{fontSize:12,color:"#9ca3af"}}>第{(pg-1)*ps+1}-{Math.min(pg*ps,list.length)}条 / 共{list.length}条</span>
          <div style={{display:"flex",gap:4}}>
            <button disabled={pg<=1} onClick={()=>setPg(pg-1)} style={{padding:"4px 8px",borderRadius:6,border:"1px solid #e5e7eb",backgroundColor:"#fff",cursor:pg<=1?"not-allowed":"pointer",opacity:pg<=1?0.4:1,fontSize:12}}>‹</button>
            {Array.from({length:Math.min(tp,7)},(_,i)=>{const p2=i+1;return<button key={p2} onClick={()=>setPg(p2)} style={{padding:"4px 10px",borderRadius:6,border:`1px solid ${pg===p2?"#6366f1":"#e5e7eb"}`,backgroundColor:pg===p2?"#6366f1":"#fff",color:pg===p2?"#fff":"#374151",fontSize:12,fontWeight:pg===p2?700:400,cursor:"pointer"}}>{p2}</button>;})}
            <button disabled={pg>=tp} onClick={()=>setPg(pg+1)} style={{padding:"4px 8px",borderRadius:6,border:"1px solid #e5e7eb",backgroundColor:"#fff",cursor:pg>=tp?"not-allowed":"pointer",opacity:pg>=tp?0.4:1,fontSize:12}}>›</button>
          </div>
        </div>
      </div>
    </div>
  );
}

// 详情页
function Detail({batchNo,onBack}) {
  const item=DATA.find(r=>r.batchNo===batchNo);
  const ea=ACTIONS[batchNo]||{};
  const [form,setForm]=useState({dept:ea.dept||"",plan:ea.plan||"",status:ea.status||"待处理",note:"",remark:ea.remark||"",amount:"",cur:"CNY",date:""});
  const [saved,setSaved]=useState(false);
  const uf=(k,v)=>setForm(p=>({...p,[k]:v}));
  const save=()=>{if(!form.dept||!form.plan){alert("请填写必填字段");return;}setSaved(true);setTimeout(()=>setSaved(false),2e3);};
  if(!item)return<div style={{padding:40,textAlign:"center",color:"#9ca3af"}}>未找到</div>;

  const Info=({l,v})=>(<div><div style={{fontSize:11,color:"#9ca3af",marginBottom:2}}>{l}</div><div style={{fontSize:14,fontWeight:500,color:"#374151"}}>{v||"-"}</div></div>);

  return (
    <div style={{padding:"20px 24px",maxWidth:1100,margin:"0 auto"}}>
      <button onClick={onBack} style={{display:"flex",alignItems:"center",gap:4,marginBottom:16,border:"none",backgroundColor:"transparent",fontSize:13,color:"#6366f1",fontWeight:600,cursor:"pointer"}}>← 返回列表</button>
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start",marginBottom:20}}>
        <div>
          <h2 style={{margin:"0 0 4px",fontSize:18,fontWeight:700,color:"#1f2937"}}>{item.materialName}</h2>
          <span style={{fontFamily:"monospace",fontSize:13,color:"#6366f1"}}>{item.materialCode}</span>
          <span style={{color:"#d1d5db",margin:"0 8px"}}>|</span>
          <span style={{fontSize:13,color:"#64748b"}}>批次 {item.batchNo}</span>
        </div>
        <div style={{display:"flex",gap:6}}><RiskTag level={item.riskLevel}/><AgingTag cat={item.agingCategory}/>{item.isFrozen===1&&<Tag color="#f59e0b" bg="#fffbeb" bd="#fde68a">已冻结</Tag>}</div>
      </div>

      <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:14,marginBottom:20}}>
        <div style={{padding:"18px 20px",borderRadius:12,backgroundColor:"#fff",border:"1px solid #f0f0f0"}}>
          <div style={{fontSize:13,fontWeight:700,color:"#374151",marginBottom:14}}>物料信息</div>
          <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:14}}><Info l="物料编号" v={item.materialCode}/><Info l="类别" v={item.rmCategory}/><Info l="物料名称" v={item.materialName}/><Info l="单位" v={item.unit}/></div>
        </div>
        <div style={{padding:"18px 20px",borderRadius:12,backgroundColor:"#fff",border:"1px solid #f0f0f0"}}>
          <div style={{fontSize:13,fontWeight:700,color:"#374151",marginBottom:14}}>存储与供应商</div>
          <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:14}}><Info l="工厂" v={item.plant}/><Info l="存储地点" v={item.storageLocDesc}/><Info l="BIN位" v={item.binLocation}/><Info l="供应商" v={item.supplierName}/></div>
        </div>
      </div>

      <div style={{display:"grid",gridTemplateColumns:"repeat(6,1fr)",gap:10,marginBottom:24}}>
        {[[" 实际库存",`${item.actualStock.toLocaleString()} ${item.unit}`],[" 重量",`${item.weightKg.toLocaleString()} KG`],[" 成本额",`¥${item.financialCost.toLocaleString()}`],[" 生产日期",item.productionDate],[" 入库日期",item.inboundDate],[" 保质期",item.expiryDate]].map(([l,v])=>(
          <div key={l} style={{padding:"12px",borderRadius:10,backgroundColor:"#fff",border:"1px solid #f0f0f0",textAlign:"center"}}>
            <div style={{fontSize:11,color:"#9ca3af",marginBottom:4}}>{l}</div><div style={{fontSize:13,fontWeight:700,color:"#1f2937"}}>{v}</div>
          </div>
        ))}
      </div>

      <div style={{padding:"24px",borderRadius:12,backgroundColor:"#fff",border:"1px solid #f0f0f0"}}>
        <div style={{display:"flex",justifyContent:"space-between",marginBottom:20}}>
          <div style={{fontSize:15,fontWeight:700,color:"#1f2937"}}>处理信息</div>
          {ea.updatedBy&&<span style={{fontSize:12,color:"#9ca3af"}}>上次更新：{ea.updatedBy} · {ea.updatedAt}</span>}
        </div>
        <div style={{display:"grid",gridTemplateColumns:"1fr 1fr 1fr",gap:18,marginBottom:18}}>
          <Sel label="责任部门" value={form.dept} onChange={v=>uf("dept",v)} options={DEPTS} required/>
          <Sel label="处理方案" value={form.plan} onChange={v=>uf("plan",v)} options={PLANS} required/>
          <Sel label="处理状态" value={form.status} onChange={v=>uf("status",v)} options={STATUSES} required/>
        </div>
        <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:18,marginBottom:18}}>
          <Inp label="线下原因补充说明" value={form.note} onChange={v=>uf("note",v)} placeholder="如有线下原因请补充..." multi/>
          <Inp label="备注（投诉单号等）" value={form.remark} onChange={v=>uf("remark",v)} placeholder="如：C202601130009" multi/>
        </div>
        <div style={{display:"grid",gridTemplateColumns:"1fr 1fr 1fr",gap:18,marginBottom:24}}>
          <Inp label="索赔金额" value={form.amount} onChange={v=>uf("amount",v)} placeholder="0.00" type="number"/>
          <Sel label="币种" value={form.cur} onChange={v=>uf("cur",v)} options={["CNY","IDR"]}/>
          <Inp label="预计完成时间" value={form.date} onChange={v=>uf("date",v)} type="date"/>
        </div>
        <div style={{display:"flex",gap:10,justifyContent:"flex-end"}}>
          <button onClick={onBack} style={{padding:"9px 22px",borderRadius:10,border:"1.5px solid #e5e7eb",fontSize:14,fontWeight:600,color:"#6b7280",backgroundColor:"#fff",cursor:"pointer"}}>取消</button>
          <button onClick={save} style={{padding:"9px 26px",borderRadius:10,border:"none",fontSize:14,fontWeight:600,color:"#fff",background:saved?"#10b981":"linear-gradient(135deg,#6366f1,#4f46e5)",cursor:"pointer",boxShadow:"0 4px 12px rgba(99,102,241,0.25)"}}>
            {saved?"✓ 已保存":"保存"}
          </button>
        </div>
      </div>
    </div>
  );
}

// 主应用
export default function App() {
  const [user,setUser]=useState(null);
  const [page,setPage]=useState("inventory");
  const [batch,setBatch]=useState(null);
  if(!user)return<Login onLogin={setUser}/>;
  return (
    <div style={{minHeight:"100vh",backgroundColor:"#f6f7f9",fontFamily:"'Noto Sans SC',-apple-system,sans-serif"}}>
      <Nav user={user} onLogout={()=>setUser(null)} page={page} onNav={p=>{setPage(p);setBatch(null);}}/>
      {page==="detail"&&batch?<Detail batchNo={batch} onBack={()=>{setBatch(null);setPage("inventory");}}/>
        :page==="pending"?<div style={{padding:40,textAlign:"center",color:"#9ca3af",fontSize:14}}>🚧 待处理页面 - 第二轮开发</div>
        :page==="upload"?<div style={{padding:40,textAlign:"center",color:"#9ca3af",fontSize:14}}>📤 数据上传页面 - 第二轮开发</div>
        :<ListPage onView={b=>{setBatch(b);setPage("detail");}}/>}
    </div>
  );
}
