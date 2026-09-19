import type { RouteObject } from "react-router-dom";
import { createBrowserRouter } from "react-router-dom";

import { App, HomePage, NotFoundPage } from "./App";

export const routes: RouteObject[] = [
  {
    path: "/",
    element: <App />,
    children: [
      { index: true, element: <HomePage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
];

export const router = createBrowserRouter(routes);
