import type { RouteObject } from "react-router-dom";
import { createBrowserRouter } from "react-router-dom";

import { App, NotFoundPage } from "./App";
import { LandingPage } from "../features/demo/LandingPage";

export const routes: RouteObject[] = [
  {
    path: "/",
    element: <App />,
    children: [
      { index: true, element: <LandingPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
];

export const router = createBrowserRouter(routes);
