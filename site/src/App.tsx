import { lazy, Suspense } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { TooltipProvider } from "./components/Tooltip";
import { Account } from "./pages/Account";
import { Home } from "./pages/Home";
import { LessonPage } from "./pages/Lesson";
import { Lessons } from "./pages/Lessons";
import { Notes } from "./pages/Notes";
import { Path } from "./pages/Path";
import { Review } from "./pages/Review";
import { Status } from "./pages/Status";
import { TaskPage } from "./pages/Task";
import { Welcome } from "./pages/Welcome";

const Results = lazy(() => import("./pages/Results"));

export function App() {
  return (
    <BrowserRouter>
      <TooltipProvider>
        <Layout>
          <Suspense fallback={<p className="muted">Loading…</p>}>
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/welcome" element={<Welcome />} />
              <Route path="/path" element={<Path />} />
              <Route path="/tasks/:id" element={<TaskPage />} />
              <Route path="/lessons" element={<Lessons />} />
              <Route path="/lessons/:id" element={<LessonPage />} />
              <Route path="/review" element={<Review />} />
              <Route path="/results" element={<Results />} />
              <Route path="/notes" element={<Notes />} />
              <Route path="/status" element={<Status />} />
              <Route path="/account" element={<Account />} />
              <Route path="*" element={<p>Page not found. <a href="/">Home</a></p>} />
            </Routes>
          </Suspense>
        </Layout>
      </TooltipProvider>
    </BrowserRouter>
  );
}
