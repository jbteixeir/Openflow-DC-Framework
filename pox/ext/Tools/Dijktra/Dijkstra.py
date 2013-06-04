
from priodict.priodict import priorityDictionary

def Dijkstra(G,start,end=None):

	D = {}	# distanze
	P = {}	# predecessori
	Q = priorityDictionary()
	Q[start] = 0
	
	for v in Q:
		D[v] = Q[v]
		if v == end: break
		
		for w in G[v]:
			vwLength = D[v] + G[v][w]
			if w in D:
				if vwLength < D[w]:
					raise ValueError, \
  " hai messo metriche negative"
			elif w not in Q or vwLength < Q[w]:
				Q[w] = vwLength
				P[w] = v
	
	return (D,P)
			
def shortestPath(G,start,end):
	
	D,P = Dijkstra(G,start,end)
	Path = []
	while 1:
		Path.append(end)
		if end == start: break
		end = P[end]
	Path.reverse()
	return Path

#Usage Example
#G = {'A':{'B':10, 'D':5}, 'B':{'C':1, 'D':2}, 'C':{'E':4}, 'D':{'B':3, 'C':9, 'E':2}, 'E':{'A':7, 'C':6}}
#print shortestPath (G,'A','C')