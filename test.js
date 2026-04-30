import http from 'k6/http';

export const options = {
  vus: 200,
  duration: '15s',
};

export default function () {
  http.get('http://mbaza.duckdns.org:8081/');
}