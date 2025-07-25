import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App'; // This imports your main App.js component
import reportWebVitals from './reportWebVitals';

// This finds the <div id="root"></div> in your public/index.html file
const root = ReactDOM.createRoot(document.getElementById('root'));

// This renders your App component inside that root div
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

// If you want to start measuring performance in your app, pass a function
// to log results (for example: reportWebVitals(console.log))
// or send to an analytics endpoint. Learn more: https://bit.ly/CRA-vitals
reportWebVitals();

