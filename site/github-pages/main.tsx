import { createRoot } from "react-dom/client";
import Home from "../app/page";
import { browserClient } from "./browser-client";
import "../app/globals.css";

const root = document.getElementById("root");
if (!root) throw new Error("The application root is missing");
createRoot(root).render(<Home client={browserClient} homeHref={import.meta.env.BASE_URL}/>);
