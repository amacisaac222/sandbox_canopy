# CanopyIQ Link & Functionality Test Checklist 🧪

**Testing URL:** https://canopyiq.ai

## 🏠 Homepage Links (/)
- [ ] "Try Live Demo" button scrolls to demo section
- [ ] "5-Min Setup" button scrolls to setup section  
- [ ] "Launch Full Console" → `/admin/console`
- [ ] "Get Your API Key" → `/contact`
- [ ] "Request Beta Access" → `/contact`
- [ ] "Read Documentation" → `/documentation`
- [ ] "Get Started Free" → `/contact`
- [ ] "View Docs" → `/documentation`

## 🧭 Main Navigation (All pages)
- [ ] Logo → `/` (home)
- [ ] "← Home" (when not on home) → `/`
- [ ] "Product" → `/product`
- [ ] "Docs" → `/documentation`
- [ ] "FAQ" → `/faq`
- [ ] "Contact" → `/contact`
- [ ] "Sign In" → `/auth/login`
- [ ] "Book Demo" → `/contact`
- [ ] "Admin" link (if logged in) → `/admin`
- [ ] "Sign Out" (if logged in) → `/auth/logout`

## 📱 Mobile Navigation
- [ ] Hamburger menu toggles correctly
- [ ] All navigation links work in mobile menu
- [ ] Mobile menu closes after clicking links

## 🔐 Authentication Flow
- [ ] `/auth/login` → redirects to `/auth/local/login` (local auth)
- [ ] Local login with `admin@canopyiq.ai` / `Admin123`
- [ ] Successful login → `/admin`
- [ ] Logout → `/auth/logout` → home page

## 👨‍💼 Admin Dashboard (/admin)
**First-time user experience:**
- [ ] Onboarding modal appears for new users
- [ ] Can select agent types (Customer Service, Data Analysis, Financial, Marketing)
- [ ] Can select starter policy (High-Risk Approval, Monitor Only, Financial Protection)
- [ ] "Skip for now" works
- [ ] Modal completion saves to localStorage
- [ ] Returns users don't see onboarding modal

**Dashboard functionality:**
- [ ] Stats cards display correctly
- [ ] "Launch Console" button → `/admin/console`
- [ ] Getting Started links work:
  - [ ] "Open Console" → `/admin/console`
  - [ ] "View Docs" → `/documentation`
  - [ ] "Contact Us" → `/contact`
- [ ] System Tools links work:
  - [ ] "Contact Submissions" → `/admin/submissions`
  - [ ] "Audit Log" → `/admin/audit`
  - [ ] "Settings" → `/admin/settings`

## 🎮 Console Interface (/admin/console)
**Main Console:**
- [ ] Console dashboard loads with stats and activity
- [ ] Quick Actions work:
  - [ ] "Access Control" → `/admin/console/access`
  - [ ] "Approval Queue" → `/admin/console/approvals`
  - [ ] "Policy Management" → `/admin/console/policy`

**Access Control (/admin/console/access):**
- [ ] Real-time access request cards display
- [ ] "Approve" buttons show toast notifications
- [ ] "Deny" buttons show toast notifications

**Approval Queue (/admin/console/approvals):**
- [ ] Filter tabs work (Pending, Approved, Denied, All)
- [ ] Approval form submissions work
- [ ] Priority-based card layout displays correctly

**Policy Management (/admin/console/policy):**
- [ ] Policy cards display with rules
- [ ] "Edit" buttons show info toast
- [ ] "Test" buttons → simulator with policy parameter
- [ ] Template buttons show creation toast

**Agent Traces (/admin/console/traces):**
- [ ] Live trace cards with step-by-step progress
- [ ] "Details" buttons show info toast
- [ ] "Pause" buttons show confirmation

**Agent Management (/admin/console/agents):**
- [ ] Agent fleet cards with status indicators
- [ ] "Pause"/"Activate" buttons work with confirmation
- [ ] "Details" buttons show info toast
- [ ] Quick deploy buttons work with confirmation

## 📚 Documentation (/documentation)
- [ ] Main docs page loads
- [ ] "← Main Site" button appears and works
- [ ] CSS and JavaScript assets load correctly (no MIME errors)
- [ ] Navigation within docs works
- [ ] Search functionality works

## 📞 Contact Form (/contact)
- [ ] Form displays correctly
- [ ] Required field validation works
- [ ] Form submission shows success message
- [ ] Redirects properly after submission

## 📋 Admin Pages
**Submissions (/admin/submissions):**
- [ ] Recent submissions display
- [ ] Pagination works if applicable

**Audit Log (/admin/audit):**
- [ ] Recent activity displays
- [ ] Log entries formatted correctly

**Settings (/admin/settings):**
- [ ] Settings page loads
- [ ] Current settings display

## 🔗 Footer Links
- [ ] Logo → `/`
- [ ] "Overview" → `/product`
- [ ] "Docs" → `/documentation`
- [ ] "Contact" → `/contact`
- [ ] "FAQ" → `/faq`
- [ ] "Terms" → `/terms`
- [ ] "Privacy" → `/privacy`

## 🧪 Interactive Demos
**Homepage Live Demo:**
- [ ] Database demo shows steps and prevention
- [ ] Financial demo shows approval workflow
- [ ] Email demo shows bulk restriction
- [ ] API demo shows monitoring

**Console Simulators:**
- [ ] Policy simulator (/admin/console/simulator) loads
- [ ] Simulation form works
- [ ] Results display correctly

## 📱 Responsive Design
- [ ] Homepage mobile layout works
- [ ] Admin interface responsive
- [ ] Console mobile-friendly
- [ ] Navigation collapses properly on mobile

## 🚨 Error Handling
- [ ] 404 page displays for invalid URLs
- [ ] Broken links show appropriate errors
- [ ] Authentication errors handled gracefully
- [ ] Form validation errors display clearly

## ⚡ Performance & Assets
- [ ] Page load times under 3 seconds
- [ ] Images load correctly
- [ ] CSS styling applies properly
- [ ] JavaScript functionality works
- [ ] No console errors in browser dev tools
- [ ] MIME type errors resolved

## 🔄 User Flows
**New visitor → Admin:**
1. [ ] Home → Contact → Admin login → Onboarding → Console
2. [ ] Home → Try Demo → Console → Contact

**Returning admin:**
1. [ ] Home → Sign In → Dashboard → Console features
2. [ ] Direct admin access → Skip onboarding → Use tools

## 🛠️ Final Verification
- [ ] All critical paths work end-to-end
- [ ] Toast notifications display properly
- [ ] Local storage saves/loads correctly
- [ ] Form submissions complete successfully
- [ ] Mobile experience is usable
- [ ] Loading states appear where appropriate

---

**Test Result:** ✅ PASS / ❌ FAIL
**Date:** ___________
**Notes:** ___________