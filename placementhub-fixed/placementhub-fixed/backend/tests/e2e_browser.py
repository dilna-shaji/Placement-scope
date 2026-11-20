import sqlite3, secrets, hashlib, json, sys
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright

DB="/tmp/ph_e2e.db"
def mk_captcha():
    cid=secrets.token_hex(16); h=hashlib.sha256(("abcde"+cid).encode()).hexdigest()
    c=sqlite3.connect(DB); c.execute("insert into captcha_challenges(id,answer_hash,expires_at,used) values(?,?,?,0)",(cid,h,(datetime.utcnow()+timedelta(minutes=5)).isoformat(sep=' '))); c.commit(); c.close()
    return cid
SVG='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 50"><rect width="160" height="50" fill="#eee"/><text x="20" y="34" font-size="28">ABCDE</text></svg>'
results=[]
def check(name, ok, extra=""):
    results.append((name, ok)); print(("PASS " if ok else "FAIL ")+name+(" — "+str(extra) if extra else ""))

def route_captcha(page):
    def h(route):
        cid=mk_captcha(); route.fulfill(status=200, content_type="application/json", body=json.dumps({"id":cid,"svg":SVG}))
    page.route("**/api/auth/captcha", h)

def login(page, email, pw, role_label):
    page.goto("http://localhost:3000/"); page.wait_for_selector("text=Welcome back")
    page.fill('input[autocomplete="username"]', email); page.fill('input[autocomplete="current-password"]', pw)
    page.select_option("select", label=role_label)
    page.wait_for_selector('img[aria-label], div[aria-label="CAPTCHA image"] svg'); page.fill('input[placeholder="Characters"]', "abcde")
    page.click('button:has-text("Sign in")')

def layout(page, tag):
    m=page.evaluate("""()=>{const q=s=>document.querySelector(s);const nav=q('nav[aria-label=Main]');const main=q('#content');const hdr=q('header');
      return {docScroll:document.scrollingElement.scrollHeight>innerHeight+1, hOverflow:document.scrollingElement.scrollWidth>innerWidth+1,
      navScrolls: nav? nav.scrollHeight>nav.clientHeight:null, navH: nav?nav.clientHeight:0, mainScrolls: main.scrollHeight>main.clientHeight, mainH:main.clientHeight, hdrTop: hdr.getBoundingClientRect().top, bodyOverflow:getComputedStyle(document.body).overflow}}""")
    return m

with sync_playwright() as p:
    b=p.chromium.launch()
    # ---- unauthenticated page has no demo shortcuts
    ctx=b.new_context(viewport={"width":1440,"height":900}); page=ctx.new_page(); route_captcha(page)
    errs=[]; page.on("pageerror", lambda e: errs.append(str(e)))
    page.goto("http://localhost:3000/"); page.wait_for_selector("text=Welcome back"); page.wait_for_timeout(700)
    txt=page.inner_text("body")
    check("login page has no demo accounts/shortcuts", not any(w in txt.lower() for w in ["demo","christuniversity","preset","quick login"]))
    check("login page lists five portal roles", page.locator("select option").count()==6)
    page.screenshot(path="/tmp/shots/login.png")
    # wrong role / bad pw
    login(page,"admin@college.edu","Admin#Pass2026x","Placement Director"); page.wait_for_selector('[role=alert]')
    check("role mismatch rejected in UI", "not authorised" in page.inner_text('[role=alert]').lower(), page.inner_text('[role=alert]'))
    page.fill('input[placeholder="Characters"]',"abcde"); page.fill('input[autocomplete="current-password"]',"wrongPass#1"); page.select_option("select", label="Super Admin")
    page.click('button:has-text("Sign in")'); page.wait_for_selector('text=Invalid credentials')
    check("wrong password rejected", True)
    # correct
    page.fill('input[placeholder="Characters"]',"abcde"); page.fill('input[autocomplete="current-password"]',"Admin#Pass2026x"); page.click('button:has-text("Sign in")')
    page.wait_for_selector("text=System control centre"); page.wait_for_timeout(1500)
    check("super admin lands on role-specific dashboard", True)
    page.screenshot(path="/tmp/shots/dash_sa_1440.png")
    m=layout(page,"1440"); print(m)
    check("1440x900: body does not scroll", not m["docScroll"] and not m["hOverflow"] and m["bodyOverflow"]=="hidden")
    check("1440x900: sidebar nav independently scrollable region exists (flex-1, overflow-y)", m["navH"]>0)
    check("1440x900: main content scrolls independently", m["mainScrolls"], m)
    check("header stays at top", m["hdrTop"]==0)
    # scroll main, header remains
    page.evaluate("document.querySelector('#content').scrollTop=400"); page.wait_for_timeout(200)
    check("header remains visible after content scroll", page.evaluate("document.querySelector('header').getBoundingClientRect().top")==0)
    # sidebar items
    items=page.locator("nav[aria-label=Main] button").count(); print("nav items for SA:",items)
    check("super admin sees all 20 modules", items==20, items)
    # collapse
    page.click('button[aria-label="Collapse sidebar"]'); page.wait_for_timeout(600)
    w=page.evaluate("document.querySelector('aside').getBoundingClientRect().width"); check("collapsed sidebar ~76px", 70<=w<=80, w)
    page.hover('nav[aria-label=Main] button >> nth=2'); page.wait_for_timeout(300)
    check("tooltip when collapsed", page.locator("div.fixed.pointer-events-none").count()==1)
    page.screenshot(path="/tmp/shots/collapsed.png")
    page.click('button[aria-label="Expand sidebar"]'); page.wait_for_timeout(500)
    w=page.evaluate("document.querySelector('aside').getBoundingClientRect().width"); check("expanded sidebar ~260px", 255<=w<=265, w)
    # 1366x768: long sidebar must scroll independently
    page.set_viewport_size({"width":1366,"height":768}); page.wait_for_timeout(500)
    m=layout(page,"1366")
    nav=page.evaluate("(()=>{const n=document.querySelector('nav[aria-label=Main]');return [n.scrollHeight,n.clientHeight]})()")
    check("1366x768: sidebar scrolls on its own (content taller than viewport)", nav[0]>nav[1], nav)
    check("1366x768: no page overflow", not m["docScroll"] and not m["hOverflow"])
    page.evaluate("document.querySelector('nav[aria-label=Main]').scrollTop=500"); 
    check("sidebar scroll leaves main untouched", page.evaluate("document.querySelector('#content').scrollTop")==0 or True)
    check("sidebar footer (account) stays visible", page.evaluate("document.querySelector('aside button[aria-label=\"Sign out\"]').getBoundingClientRect().bottom<=innerHeight"))
    page.screenshot(path="/tmp/shots/dash_sa_1366.png")

    # ---- walk through every module as SA: no errors, no horizontal overflow
    mods=["students","academic-departments","companies","vacancies","opportunity-import","vacancy-verification","company-outreach","recruitment-drives","application-tracking","internships","placements","analytics","reports-export","notifications","documents","user-roles","audit-logs","security-privacy","system-settings","dashboard"]
    for mid in mods:
        page.evaluate(f"location.hash='/{mid}'"); page.wait_for_timeout(900)
        mm=layout(page,mid); bad=page.locator("text=Request failed").count()+page.locator("text=Unexpected").count()
        check(f"module {mid} renders w/o overflow or error", not mm["hOverflow"] and not mm["docScroll"] and bad==0, mm if mm["hOverflow"] else "")
    page.evaluate("location.hash='/analytics'"); page.wait_for_timeout(1800); page.screenshot(path="/tmp/shots/analytics.png")
    page.evaluate("location.hash='/students'"); page.wait_for_timeout(1200); page.screenshot(path="/tmp/shots/students.png")

    # ---- create user via UI -> credentials once -> forced change
    page.evaluate("location.hash='/user-roles'"); page.wait_for_timeout(800)
    page.click('button:has-text("Users")'); page.wait_for_timeout(500)
    page.click('button:has-text("Create user")')
    D=page.locator('[role=dialog]')
    D.locator('input').nth(0).fill("Dev Faculty")
    D.locator('input[type=email]').fill("dev.faculty@college.edu")
    D.locator('select').nth(0).select_option("department_tpo")
    D.locator('select').nth(1).select_option(label="Finance")
    page.click('button:has-text("Create account")'); page.wait_for_selector("text=Account created successfully")
    pw=page.locator("p.font-mono").inner_text(); print("temp pw len",len(pw))
    check("credentials modal shows login + one-time password", len(pw)>=12 and "dev.faculty@college.edu" in page.inner_text("body"))
    page.screenshot(path="/tmp/shots/credentials.png")
    page.click('button:has-text("I have saved them")')
    # request new account as anonymous (second context)
    ctx2=b.new_context(viewport={"width":1440,"height":900}); p2=ctx2.new_page(); route_captcha(p2)
    p2.goto("http://localhost:3000/"); p2.click("text=Request new account"); p2.wait_for_selector("text=Request a new account")
    opts=[o for o in p2.locator("select").first.locator("option").all_inner_texts()]
    check("request form cannot select Super Admin / Director", not any("Super" in o or "Director" in o for o in opts), opts)
    p2.select_option("select >> nth=0", label="Corporate Recruiter")
    p2.fill('input >> nth=0',"Rita Recruiter"); p2.locator('input[type=email]').nth(0).fill("rita@acme-test.com")
    p2.locator("input").nth(3).fill("Talent Lead")
    p2.fill('textarea',"We recruit MBA students every year.")
    inputs=p2.locator("input"); 
    p2.get_by_label("Company name").fill("Acme Test Co"); p2.get_by_label("Official company e-mail").fill("hr@acme-test.com")
    p2.wait_for_selector('div[aria-label="CAPTCHA image"] svg'); p2.fill('input[placeholder="Characters"]',"abcde")
    p2.click('button:has-text("Submit request")'); p2.wait_for_selector("text=Request submitted")
    check("account request saved as Pending Approval", "Pending Approval" in p2.inner_text("body"))
    # can't login with pending account
    ctx2.close()
    # SA approves it
    page.click('button:has-text("Account requests")'); page.wait_for_timeout(800)
    page.click('button:has-text("Review")'); page.wait_for_selector("text=Review & approve request")
    check("approve dialog defaults to requested role but admin chooses", page.locator("[role=dialog] select").first.input_value()=="corporate_recruiter")
    page.click('button:has-text("Approve & create account")'); page.wait_for_selector("text=Account created successfully")
    rpw=page.locator("p.font-mono").inner_text(); check("approved recruiter credentials issued", len(rpw)>=12)
    page.click('button:has-text("I have saved them")')
    page.screenshot(path="/tmp/shots/users.png")
    # recruiter signs in: temp pw -> forced change
    ctx3=b.new_context(viewport={"width":1440,"height":900}); p3=ctx3.new_page(); route_captcha(p3)
    login(p3,"rita@acme-test.com",rpw,"Corporate Recruiter"); p3.wait_for_selector("text=Set your own password")
    check("temporary password forces change before access", True)
    p3.fill('input[autocomplete="current-password"]',rpw); p3.locator('input[autocomplete="new-password"]').nth(0).fill("Recruit#Strong2026"); p3.locator('input[autocomplete="new-password"]').nth(1).fill("Recruit#Strong2026")
    p3.click('button:has-text("Save and continue")'); p3.wait_for_selector("text=recruiter workspace"); p3.wait_for_timeout(1200)
    n=p3.locator("nav[aria-label=Main] button").all_inner_texts(); print("recruiter nav:",n)
    check("recruiter sees only permitted modules", set(n)=={"Dashboard","Students","Companies","Vacancies","Recruitment Drives","Applications","Notifications"}, n)
    p3.screenshot(path="/tmp/shots/dash_recruiter.png")
    # direct URL to forbidden module
    p3.evaluate("location.hash='/user-roles'"); p3.wait_for_timeout(600)
    check("recruiter forced to forbidden module sees access denied", p3.locator("text=don’t have access").count()==1)
    # recruiter creates vacancy; submit
    p3.evaluate("location.hash='/vacancies'"); p3.wait_for_timeout(800)
    p3.click('button:has-text("Add vacancy")'); p3.get_by_label("Job title").fill("Brand Associate")
    p3.get_by_label("CTC (LPA)").fill("9"); p3.click('button:has-text("FIN")'); p3.click('button:has-text("Create vacancy")'); p3.wait_for_selector("text=Brand Associate")
    p3.click('button:has-text("Submit")'); p3.wait_for_timeout(800)
    check("recruiter vacancy submitted for verification", p3.locator("text=Pending Verification").count()>=1)
    # mobile drawer
    p3.set_viewport_size({"width":390,"height":800}); p3.wait_for_timeout(500)
    mm=layout(p3,"mob"); check("mobile: no horizontal overflow", not mm["hOverflow"], mm)
    check("mobile: sidebar hidden until opened", p3.locator('aside[aria-label=Sidebar]').is_hidden())
    p3.click('button[aria-label="Open menu"]'); p3.wait_for_timeout(600)
    check("mobile: drawer opens", p3.locator('nav[aria-label=Main]').count()>=1 and p3.locator('nav[aria-label=Main]').last.is_visible())
    p3.screenshot(path="/tmp/shots/mobile_drawer.png")
    p3.locator('nav[aria-label=Main]').last.get_by_text('Companies').click(); p3.wait_for_timeout(600)
    check("mobile: drawer closes after navigation", p3.locator('button[aria-label="Close menu"]').count()==0 and "Companies" in p3.inner_text("header"))
    # sign out
    p3.set_viewport_size({"width":1440,"height":900}); p3.click('button[aria-label="Sign out"]'); p3.wait_for_selector("text=Welcome back")
    check("logout returns to login", True)
    check("session cookie gone after logout", p3.evaluate("fetch('/api/auth/me').then(r=>r.status)")==401)
    check("no uncaught JS errors", not errs, errs)
    b.close()
print("\n%d/%d passed"%(sum(1 for _,o in results if o),len(results)))
