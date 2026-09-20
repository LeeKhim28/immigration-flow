import type { RouteObject } from "react-router-dom";
import { createBrowserRouter } from "react-router-dom";

import { App, NotFoundPage } from "./App";
import { LandingPage } from "../features/demo/LandingPage";
import { ApplicantLayout } from "../features/applicant/ApplicantLayout";
import { EvaluationRoute, HandoverRoute, OverviewRoute, RequirementsRoute } from "../features/applicant/ApplicantRoutes";
import { OfficerLayout } from "../features/officer/OfficerLayout";
import { CaseRoute, QueueRoute } from "../features/officer/OfficerRoutes";

export const routes: RouteObject[] = [
  {
    path: "/",
    element: <App />,
    children: [
      { index: true, element: <LandingPage /> },
      { path: "applicant/cases/:caseId", element: <ApplicantLayout />, children: [
        { index: true, element: <OverviewRoute /> },
        { path: "requirements", element: <RequirementsRoute /> },
        { path: "evaluation", element: <EvaluationRoute /> },
        { path: "handover", element: <HandoverRoute /> },
      ] },
      { path: "officer/cases", element: <OfficerLayout />, children: [
        { index: true, element: <QueueRoute /> },
        { path: ":caseId", element: <CaseRoute /> },
      ] },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
];

export const router = createBrowserRouter(routes);
