import { Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis, Area, AreaChart, ComposedChart } from 'recharts';

export const PALETTE = ['#2457A7', '#16877A', '#D99020', '#C44747', '#142B4A'];
const axis = { fontSize: 12, fill: '#64748B' };
const tip = { contentStyle: { borderRadius: 14, border: '1px solid #DFE6EF', boxShadow: '0 12px 30px -10px rgba(20,43,74,.2)', fontSize: 13 } };

export const NoData = () => <div className="h-full grid place-items-center text-mute text-[14px]">No data for this selection yet.</div>;

export function BarC({ data, x = 'name', y = 'value', h = 260, color = 0, horizontal }: { data: any[]; x?: string; y?: string; h?: number; color?: number; horizontal?: boolean }) {
  if (!data?.length) return <div style={{ height: h }}><NoData /></div>;
  return (
    <ResponsiveContainer width="100%" height={h}>
      <BarChart data={data} layout={horizontal ? 'vertical' : 'horizontal'} margin={{ left: horizontal ? 20 : -14, right: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#EEEAF8" vertical={false} horizontal={!horizontal} />
        {horizontal ? <><XAxis type="number" tick={axis} axisLine={false} tickLine={false} /><YAxis type="category" dataKey={x} tick={axis} width={110} axisLine={false} tickLine={false} /></>
          : <><XAxis dataKey={x} tick={axis} axisLine={false} tickLine={false} /><YAxis tick={axis} axisLine={false} tickLine={false} allowDecimals={false} /></>}
        <Tooltip {...tip} cursor={{ fill: 'rgba(36,87,167,.08)' }} />
        <Bar dataKey={y} radius={horizontal ? [0, 8, 8, 0] : [8, 8, 0, 0]} animationDuration={900}>
          {data.map((_, i) => <Cell key={i} fill={PALETTE[(color + i) % PALETTE.length]} />)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

export function LineC({ data, x = 'name', y = 'value', h = 260, area }: { data: any[]; x?: string; y?: string; h?: number; area?: boolean }) {
  if (!data?.length) return <div style={{ height: h }}><NoData /></div>;
  return (
    <ResponsiveContainer width="100%" height={h}>
      {area ? (
        <AreaChart data={data} margin={{ left: -14, right: 8 }}>
          <defs><linearGradient id="ag" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#2457A7" stopOpacity={.45} /><stop offset="100%" stopColor="#2457A7" stopOpacity={0} /></linearGradient></defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#DFE6EF" vertical={false} /><XAxis dataKey={x} tick={axis} axisLine={false} tickLine={false} /><YAxis tick={axis} axisLine={false} tickLine={false} allowDecimals={false} /><Tooltip {...tip} />
          <Area type="monotone" dataKey={y} stroke="#2457A7" strokeWidth={3} fill="url(#ag)" animationDuration={1000} />
        </AreaChart>
      ) : (
        <LineChart data={data} margin={{ left: -14, right: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#DFE6EF" vertical={false} /><XAxis dataKey={x} tick={axis} axisLine={false} tickLine={false} /><YAxis tick={axis} axisLine={false} tickLine={false} allowDecimals={false} /><Tooltip {...tip} />
          <Line type="monotone" dataKey={y} stroke="#2457A7" strokeWidth={3} dot={{ r: 4, fill: '#fff', strokeWidth: 2 }} activeDot={{ r: 7 }} animationDuration={1000} />
        </LineChart>
      )}
    </ResponsiveContainer>
  );
}

export function PieC({ data, h = 260 }: { data: any[]; h?: number }) {
  if (!data?.length || data.every((d) => !d.value)) return <div style={{ height: h }}><NoData /></div>;
  return (
    <ResponsiveContainer width="100%" height={h}>
      <PieChart>
        <Pie data={data} dataKey="value" nameKey="name" innerRadius="55%" outerRadius="82%" paddingAngle={3} animationDuration={900} stroke="none">
          {data.map((_, i) => <Cell key={i} fill={PALETTE[i % PALETTE.length]} />)}
        </Pie>
        <Tooltip {...tip} /><Legend iconType="circle" wrapperStyle={{ fontSize: 13 }} />
      </PieChart>
    </ResponsiveContainer>
  );
}

export function MultiBar({ data, keys, h = 280 }: { data: any[]; keys: { key: string; name: string; color: string; line?: boolean }[]; h?: number }) {
  if (!data?.length) return <div style={{ height: h }}><NoData /></div>;
  return (
    <ResponsiveContainer width="100%" height={h}>
      <ComposedChart data={data} margin={{ left: -14, right: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#DFE6EF" vertical={false} />
        <XAxis dataKey="name" tick={axis} axisLine={false} tickLine={false} /><YAxis tick={axis} axisLine={false} tickLine={false} />
        <Tooltip {...tip} /><Legend iconType="circle" wrapperStyle={{ fontSize: 13 }} />
        {keys.map((k) => k.line ? <Line key={k.key} dataKey={k.key} name={k.name} stroke={k.color} strokeWidth={3} dot={{ r: 4 }} /> : <Bar key={k.key} dataKey={k.key} name={k.name} fill={k.color} radius={[6, 6, 0, 0]} />)}
      </ComposedChart>
    </ResponsiveContainer>
  );
}
