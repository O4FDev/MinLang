import Dispatch
let n = COUNT
let keys: [KEY_TYPE] = (0..<n).map { i in KEY_EXPR }
let queries: [KEY_TYPE] = (0..<n).map { i in KEY_EXPR }
var m: [KEY_TYPE: Int] = [:]
var start = DispatchTime.now().uptimeNanoseconds
for i in 0..<n { m[keys[i]] = i * 3 + 1 }
let inserted = DispatchTime.now().uptimeNanoseconds - start
start = DispatchTime.now().uptimeNanoseconds
var sum = 0
for i in 0..<n { let k = i * 104729 % n; sum += m[queries[k]]! }
let looked = DispatchTime.now().uptimeNanoseconds - start
start = DispatchTime.now().uptimeNanoseconds
for i in 0..<n {
    let k = i * 104729 % n
    if i % 2 == 0 { m[keys[k]] = m[queries[k]]! + 5 }
    else { precondition(m.removeValue(forKey: queries[k]) != nil); m[keys[k]] = k * 3 + 2 }
}
let mixed = DispatchTime.now().uptimeNanoseconds - start
start = DispatchTime.now().uptimeNanoseconds
for i in 0..<n { let k = i * 104729 % n; precondition(m.removeValue(forKey: queries[k]) != nil) }
let removed = DispatchTime.now().uptimeNanoseconds - start
print(inserted)
print(looked)
print(mixed)
print(removed)
print(sum)
print(m.count)
